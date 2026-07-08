import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:msgpack_dart/msgpack_dart.dart' as msgpack;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/ai_data.dart';
import '../models/signal_data.dart';
import '../utils/ar_labels.dart';

const _signalsStorageKey = 'detected_signals_v1';

// FC0013 tuner lockable range — the backend enforces the same limits;
// this guard just gives instant feedback without a round-trip.
const tunerMinMhz = 14.0;
const tunerMaxMhz = 948.0;

class SdrService extends ChangeNotifier {
  WebSocketChannel? _channel;
  bool _connected = false;
  String _piAddress = '192.168.11.125';
  int _piPort = 8765;

  final List<SignalData> _detectedSignals = [];
  final ValueNotifier<SpectrumFrame?> spectrumNotifier = ValueNotifier(null);
  final ValueNotifier<List<double>> waveformNotifier = ValueNotifier(const []);
  String _status = 'غير متصل';
  double _centerFreq = 100.0;
  bool _isScanning = false;

  final FlutterTts _tts = FlutterTts();
  bool _voiceEnabled = true;
  final Set<String> _announcedFreqs = {};

  // AI tab state: current signal analysis reuses the latest SignalData
  // (already carries type/confidence/reason), plus audio classification,
  // captures history and on-demand speech-to-text — all backend-driven,
  // this class holds no analysis logic of its own.
  SignalData? _latestAnalysis;
  AudioClassification? _latestAudioClass;
  final List<CaptureEntry> _captures = [];
  bool _sttActive = false;
  String? _lastSttText;
  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();
  bool _notificationsReady = false;

  // AI dashboard: live engine status + bounded event timeline, both
  // derived purely from backend messages (no analysis logic here).
  String _aiStatus = 'جاهز';
  Timer? _aiStatusRevert;
  final List<AiEvent> _aiEvents = [];

  String get aiStatus => _aiStatus;
  List<AiEvent> get aiEvents => List.unmodifiable(_aiEvents);

  // Stage-1 status while nothing is detected: band identity of the
  // current tuning, noise floor, occupancy — keeps the AI cards alive.
  Map<String, dynamic>? _bandStatus;
  Map<String, dynamic>? get bandStatus => _bandStatus;

  // Adaptive monitoring: user-selected profile elevates the displayed
  // priority of matching band categories by one level. Display-side only
  // — the backend's context priority is never overwritten.
  static const monitoringProfiles = [
    'عام', 'الطيران', 'بحري', 'أجهزة ISM', 'الهواة', 'الأقمار الصناعية', 'الخلوي',
  ];
  static const _profileCategoryKeyword = {
    'الطيران': 'aviation',
    'بحري': 'maritime',
    'أجهزة ISM': 'short-range',
    'الهواة': 'amateur',
    'الأقمار الصناعية': 'satellite',
    'الخلوي': 'cellular',
  };
  static const _priorityOrder = ['Low', 'Medium', 'High', 'Critical'];
  String _monitoringProfile = 'عام';
  String get monitoringProfile => _monitoringProfile;

  Future<void> setMonitoringProfile(String profile) async {
    _monitoringProfile = profile;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('monitoring_profile_v1', profile);
    } catch (_) {}
  }

  Future<void> _loadMonitoringProfile() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final p = prefs.getString('monitoring_profile_v1');
      if (p != null && monitoringProfiles.contains(p)) {
        _monitoringProfile = p;
        notifyListeners();
      }
    } catch (_) {}
  }

  /// (level, boostedByProfile): backend priority, elevated one step when
  /// the signal's band category matches the selected monitoring profile.
  (String, bool) effectivePriority(SignalData s) {
    final base = s.priority ?? 'Unknown';
    final keyword = _profileCategoryKeyword[_monitoringProfile];
    if (keyword == null) return (base, false);
    final category =
        (s.bandInfo?['knowledge']?['category'] ?? '').toString().toLowerCase();
    if (!category.contains(keyword)) return (base, false);
    final i = _priorityOrder.indexOf(base);
    if (i < 0) return ('Medium', true); // Unknown but profile-relevant
    return (_priorityOrder[(i + 1).clamp(0, _priorityOrder.length - 1)], i < _priorityOrder.length - 1);
  }

  SignalData? get latestAnalysis => _latestAnalysis;
  AudioClassification? get latestAudioClassification => _latestAudioClass;
  List<CaptureEntry> get captures => List.unmodifiable(_captures);
  bool get sttActive => _sttActive;
  String? get lastSttText => _lastSttText;
  String get capturesBaseUrl => 'http://$_piAddress:8766';

  // Audio is played locally on the Pi (see audio_player.py on the backend);
  // this only tracks the local toggle state for the AUDIO control and sends
  // start_audio/stop_audio/mute/unmute commands — no PCM is ever received
  // or played here.
  bool _audioMuted = true;
  bool get audioMuted => _audioMuted;

  bool get connected => _connected;
  List<SignalData> get detectedSignals => List.unmodifiable(_detectedSignals);
  SpectrumFrame? get currentSpectrum => spectrumNotifier.value;
  List<double> get waveform => waveformNotifier.value;
  String get status => _status;
  double get centerFreq => _centerFreq;
  bool get isScanning => _isScanning;
  String get piAddress => _piAddress;
  bool get voiceEnabled => _voiceEnabled;

  SdrService() {
    _loadSignals();
    _loadMonitoringProfile();
    _initTts();
    _initNotifications();
  }

  Future<void> _initNotifications() async {
    try {
      const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
      const iosInit = DarwinInitializationSettings();
      await _notifications.initialize(
        const InitializationSettings(android: androidInit, iOS: iosInit, macOS: iosInit),
      );
      _notificationsReady = true;
    } catch (e) {
      debugPrint('Notification init error: $e');
    }
  }

  Future<void> _notifyAnomaly(SignalData signal) async {
    if (!_notificationsReady) return;
    try {
      await _notifications.show(
        signal.hashCode,
        'تم اكتشاف إشارة غير اعتيادية',
        '${arType(signal.type)} على التردد ${signal.frequency.toStringAsFixed(2)} MHz '
            '(شذوذ ${(signal.anomalyScore * 100).toInt()}%)',
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'signal_alerts',
            'تنبيهات الإشارات',
            channelDescription: 'اكتشافات إشارات راديوية جديدة أو غير اعتيادية',
            importance: Importance.high,
            priority: Priority.high,
          ),
          iOS: DarwinNotificationDetails(),
        ),
      );
    } catch (e) {
      debugPrint('Notification show error: $e');
    }
  }

  void startSpeechToText() {
    if (!_connected) return;
    _send({'command': 'start_stt'});
    _sttActive = true;
    notifyListeners();
  }

  void stopSpeechToText() {
    _send({'command': 'stop_stt'});
    _sttActive = false;
    notifyListeners();
  }

  void clearCaptures() {
    _captures.clear();
    notifyListeners();
  }

  /// Tells the Pi to start/stop demodulating+playing audio locally and
  /// flips the local toggle state for the AUDIO control.
  void setAudioMuted(bool muted) {
    _audioMuted = muted;
    _send({'command': muted ? 'stop_audio' : 'start_audio', 'freq_mhz': _centerFreq});
    notifyListeners();
  }

  /// 0.0-4.0, forwarded as-is to the Pi's `play -v` volume multiplier.
  void setVolume(double volume) {
    _send({'command': 'set_volume', 'volume': volume});
  }

  Future<void> _initTts() async {
    try {
      await _tts.setLanguage('ar');
      await _tts.setVolume(1.0);
      await _tts.setSpeechRate(0.5);
      await _tts.setPitch(1.0);
      await _tts.awaitSpeakCompletion(true);
    } catch (e) {
      debugPrint('TTS init error: $e');
    }
  }

  void setAddress(String address, int port) {
    _piAddress = address;
    _piPort = port;
  }

  void setVoiceEnabled(bool enabled) {
    _voiceEnabled = enabled;
    notifyListeners();
  }

  Future<void> connect() async {
    try {
      _status = 'جارٍ الاتصال...';
      notifyListeners();

      _channel = WebSocketChannel.connect(
        Uri.parse('ws://$_piAddress:$_piPort'),
      );

      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDisconnected,
      );

      _connected = true;
      _status = 'متصل بـ $_piAddress';
      notifyListeners();
    } catch (e) {
      _status = 'خطأ: $e';
      _connected = false;
      notifyListeners();
    }
  }

  void disconnect() {
    _channel?.sink.close();
    _connected = false;
    _isScanning = false;
    _status = 'غير متصل';
    notifyListeners();
  }

  /// [demodulator] picks the backend's receive chain for this band, e.g.
  /// 'WFM' for broadcast FM, 'NFM' for analog voice radios, 'AM' for
  /// airband/HF AM, 'USB'/'LSB' for HF/ham SSB. Omit to leave the
  /// backend's current mode unchanged (e.g. repeated taps within the FM
  /// broadcast band don't need to resend it).
  /// True when the tuner can actually lock this frequency; otherwise
  /// sets an explanatory status and returns false.
  bool _checkTunable(double freqMhz) {
    if (freqMhz >= tunerMinMhz && freqMhz <= tunerMaxMhz) return true;
    _status =
        'التردد ${freqMhz.toStringAsFixed(1)} MHz غير مدعوم — مدى الموالف '
        '${tunerMinMhz.toStringAsFixed(0)}-${tunerMaxMhz.toStringAsFixed(0)} MHz';
    notifyListeners();
    return false;
  }

  void startScan({double centerFreqMhz = 100.0, String? demodulator}) {
    if (!_connected) return;
    if (!_checkTunable(centerFreqMhz)) return;
    _centerFreq = centerFreqMhz;
    _isScanning = true;
    _send({
      'command': 'start_scan',
      'center_freq_mhz': centerFreqMhz,
      if (demodulator != null) 'demodulator': demodulator,
    });
    notifyListeners();
  }

  void stopScan() {
    _isScanning = false;
    _send({'command': 'stop_scan'});
    notifyListeners();
  }

  /// See [startScan] for what [demodulator] selects.
  void setFrequency(double freqMhz, {String? demodulator}) {
    if (!_checkTunable(freqMhz)) return;
    _centerFreq = freqMhz;
    _send({
      'command': 'set_freq',
      'freq_mhz': freqMhz,
      if (demodulator != null) 'demodulator': demodulator,
    });
    notifyListeners();
  }

  void clearSignals() {
    _detectedSignals.clear();
    _announcedFreqs.clear();
    notifyListeners();
    _saveSignals();
  }

  void _onMessage(dynamic message) {
    try {
      final bytes = message is Uint8List
          ? message
          : Uint8List.fromList(message as List<int>);
      final decoded = msgpack.deserialize(bytes);
      final data = Map<String, dynamic>.from(decoded as Map);
      final type = data['type'] as String?;

      switch (type) {
        case 'spectrum':
          spectrumNotifier.value = SpectrumFrame.fromJson(data);
        case 'signal':
          final signal = SignalData.fromJson(data);
          _detectedSignals.insert(0, signal);
          if (_detectedSignals.length > 200) _detectedSignals.removeLast();
          _latestAnalysis = signal;
          _trackAiSignal(signal);
          notifyListeners();
          _saveSignals();
          _announce(signal);
          if (signal.isAnomaly) _notifyAnomaly(signal);
        case 'rf_event':
          final ev = arSentence(data['event'] as String? ?? 'حدث راديوي');
          final detail = arSentence(data['detail'] as String? ?? '');
          _pushAiEvent(AiEvent(AiEventKind.rfEvent, detail.isEmpty ? ev : '$ev — $detail'));
          _setAiStatus(ev);
          notifyListeners();
        case 'band_status':
          _bandStatus = data;
          _setAiStatus('جارٍ المسح');
          notifyListeners();
        case 'waveform':
          waveformNotifier.value = (data['samples'] as List<dynamic>)
              .map((e) => (e as num).toDouble())
              .toList();
        case 'audio_classification':
          final prevLabel = _latestAudioClass?.mixedLabel;
          _latestAudioClass = AudioClassification.fromJson(data);
          if (_latestAudioClass!.mixedLabel != prevLabel) {
            _pushAiEvent(AiEvent(AiEventKind.audio,
                'الصوت: ${arAudio(_latestAudioClass!.mixedLabel)} (${(_latestAudioClass!.confidence * 100).toInt()}%)'));
          }
          _setAiStatus('تحليل الصوت');
          notifyListeners();
        case 'capture':
          _captures.insert(0, CaptureEntry.fromJson(data));
          if (_captures.length > 100) _captures.removeLast();
          final c = _captures.first;
          _pushAiEvent(AiEvent(AiEventKind.capture,
              'تم حفظ تسجيل: ${c.frequency.toStringAsFixed(3)} MHz (${arType(c.typeLabel)})'));
          _setAiStatus('حفظ التسجيل');
          notifyListeners();
        case 'stt_text':
          _lastSttText = data['text'] as String?;
          notifyListeners();
        case 'status':
          _status = arSentence(data['message'] as String? ?? _status);
          notifyListeners();
      }
    } catch (e) {
      debugPrint('Parse error: $e');
    }
  }

  /// Derives AI dashboard status + timeline events from a detection.
  /// The interesting transitions come from the backend's fingerprint
  /// comparison (fp_status) — this only translates them for display.
  void _trackAiSignal(SignalData s) {
    final freq = s.frequency.toStringAsFixed(3);
    switch (s.fpStatus) {
      case 'new':
        _setAiStatus('تم حفظ بصمة جديدة');
        _pushAiEvent(AiEvent(
            s.isUnknown ? AiEventKind.unknownSignal : AiEventKind.newSignal,
            s.isUnknown
                ? 'إشارة مجهولة على $freq MHz — تم حفظ البصمة، أقرب تخمين: ${arType(s.type)} (${(s.confidence * 100).toInt()}%)'
                : 'إشارة جديدة: ${arType(s.type)} على $freq MHz'));
      case 'changed':
        _setAiStatus('المقارنة مع البصمة');
        _pushAiEvent(AiEvent(AiEventKind.changedSignal,
            'الإشارة على $freq MHz تغيّرت مقارنة بالبصمة: ${s.fpNotes.map(arSentence).join('؛ ')}'));
      default:
        _setAiStatus('جارٍ التحليل');
        if (s.isAnomaly) {
          _pushAiEvent(AiEvent(AiEventKind.detection,
              'شذوذ على $freq MHz (${(s.anomalyScore * 100).toInt()}%)'));
        }
    }
  }

  void _setAiStatus(String status) {
    _aiStatus = status;
    _aiStatusRevert?.cancel();
    _aiStatusRevert = Timer(const Duration(seconds: 4), () {
      _aiStatus = 'جاهز';
      notifyListeners();
    });
  }

  void _pushAiEvent(AiEvent event) {
    _aiEvents.insert(0, event);
    if (_aiEvents.length > 60) _aiEvents.removeLast();
  }

  Future<void> _announce(SignalData signal) async {
    if (!_voiceEnabled) return;
    final key = '${signal.type}@${signal.frequency.toStringAsFixed(1)}';
    if (_announcedFreqs.contains(key)) return;
    _announcedFreqs.add(key);

    final label = signal.isAnomaly
        ? 'تم اكتشاف شذوذ على التردد ${signal.frequency.toStringAsFixed(1)} ميجاهرتز'
        : 'تم اكتشاف ${arType(signal.type)} على التردد ${signal.frequency.toStringAsFixed(1)} ميجاهرتز';
    try {
      await _tts.speak(label);
    } catch (_) {}
  }

  Future<void> _loadSignals() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList(_signalsStorageKey);
      if (raw == null) return;
      _detectedSignals.clear();
      _detectedSignals.addAll(
        raw.map((e) => SignalData.fromJson(jsonDecode(e) as Map<String, dynamic>)),
      );
      notifyListeners();
    } catch (e) {
      debugPrint('Load signals error: $e');
    }
  }

  Future<void> _saveSignals() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final encoded = _detectedSignals.take(200).map((s) => jsonEncode(s.toJson())).toList();
      await prefs.setStringList(_signalsStorageKey, encoded);
    } catch (e) {
      debugPrint('Save signals error: $e');
    }
  }

  void _onError(dynamic error) {
    _connected = false;
    _isScanning = false;
    _status = 'خطأ: $error';
    notifyListeners();
  }

  void _onDisconnected() {
    _connected = false;
    _isScanning = false;
    _status = 'غير متصل';
    notifyListeners();
  }

  void _send(Map<String, dynamic> data) {
    _channel?.sink.add(msgpack.serialize(data));
  }

  @override
  void dispose() {
    _aiStatusRevert?.cancel();
    disconnect();
    spectrumNotifier.dispose();
    waveformNotifier.dispose();
    _tts.stop();
    super.dispose();
  }
}
