class SignalData {
  final double frequency;
  final double power;
  final double bandwidth;
  final DateTime time;
  final String type;
  final String classification;
  final double anomalyScore;
  final List<double> spectrum;
  final double confidence;
  final List<String> analyzerReason;
  final double? snrDb;

  // Smart-analysis report (all backend-computed, optional so older
  // backends / stored entries still parse).
  final String? modulation;
  final double? stability; // 0..1
  final String? continuity; // continuous | intermittent | new
  final bool interference;
  final double? noisePct; // 0..1
  final double? quality; // 0..1
  final double? realProb; // 0..1 probability this is a real signal
  final String? fpStatus; // new | known | changed
  final List<String> fpNotes;
  final int? seenCount;
  final DateTime? lastSeenPrior;

  // V2 smart-analysis payload (all backend-computed and optional).
  final List<SignalCandidate> candidates; // ranked top-5 hypotheses
  final Map<String, double> confidenceBreakdown; // classification/detection/...
  final List<String> noiseDiagnosis;
  final Map<String, dynamic> metrics; // deep RF metrics report
  final Map<String, dynamic>? channelInfo; // Wi-Fi channel, LTE band, ...
  final List<SatelliteGuess> satellites;
  final List<String> useHints; // possible device types (estimates)
  final Map<String, dynamic>? bandInfo; // RF band identity + occupancy + knowledge
  final String? priority; // Critical | High | Medium | Low | Unknown
  final List<String> priorityReasons;

  const SignalData({
    required this.frequency,
    required this.power,
    required this.bandwidth,
    required this.time,
    required this.type,
    required this.classification,
    required this.anomalyScore,
    required this.spectrum,
    this.confidence = 0.0,
    this.analyzerReason = const [],
    this.snrDb,
    this.modulation,
    this.stability,
    this.continuity,
    this.interference = false,
    this.noisePct,
    this.quality,
    this.realProb,
    this.fpStatus,
    this.fpNotes = const [],
    this.seenCount,
    this.lastSeenPrior,
    this.candidates = const [],
    this.confidenceBreakdown = const {},
    this.noiseDiagnosis = const [],
    this.metrics = const {},
    this.channelInfo,
    this.satellites = const [],
    this.useHints = const [],
    this.bandInfo,
    this.priority,
    this.priorityReasons = const [],
  });

  factory SignalData.fromJson(Map<String, dynamic> json) {
    return SignalData(
      frequency: (json['freq'] as num).toDouble(),
      power: (json['power'] as num).toDouble(),
      bandwidth: (json['bandwidth'] as num?)?.toDouble() ?? 0.0,
      time: DateTime.parse(json['time'] as String),
      // الباك اند يرسل نوع الرسالة في 'type' ("signal") والتصنيف الفعلي
      // في 'type_label'؛ الإشارات المحفوظة محلياً تحمل التصنيف في 'type'.
      type: json['type_label'] as String? ?? json['type'] as String? ?? 'Unknown',
      classification: json['classification'] as String? ?? 'Normal',
      anomalyScore: (json['anomaly_score'] as num?)?.toDouble() ?? 0.0,
      spectrum: (json['spectrum'] as List<dynamic>?)
              ?.map((e) => (e as num).toDouble())
              .toList() ??
          [],
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      analyzerReason: (json['analyzer_reason'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      snrDb: (json['snr_db'] as num?)?.toDouble(),
      modulation: json['modulation'] as String?,
      stability: (json['stability'] as num?)?.toDouble(),
      continuity: json['continuity'] as String?,
      interference: json['interference'] as bool? ?? false,
      noisePct: (json['noise_pct'] as num?)?.toDouble(),
      quality: (json['quality'] as num?)?.toDouble(),
      realProb: (json['real_prob'] as num?)?.toDouble(),
      fpStatus: json['fp_status'] as String?,
      fpNotes: (json['fp_notes'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      seenCount: (json['seen_count'] as num?)?.toInt(),
      lastSeenPrior: json['last_seen_prior'] != null
          ? DateTime.fromMillisecondsSinceEpoch(((json['last_seen_prior'] as num) * 1000).round())
          : null,
      candidates: (json['candidates'] as List<dynamic>?)
              ?.map((e) => SignalCandidate.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList() ??
          const [],
      confidenceBreakdown: (json['confidence_breakdown'] as Map?)?.map(
            (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
          ) ??
          const {},
      noiseDiagnosis:
          (json['noise_diagnosis'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      metrics: json['metrics'] is Map
          ? Map<String, dynamic>.from(json['metrics'] as Map)
          : const {},
      channelInfo: json['channel_info'] is Map
          ? Map<String, dynamic>.from(json['channel_info'] as Map)
          : null,
      satellites: (json['satellites'] as List<dynamic>?)
              ?.map((e) => SatelliteGuess.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList() ??
          const [],
      useHints: (json['use_hints'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      bandInfo: json['band_info'] is Map
          ? Map<String, dynamic>.from(json['band_info'] as Map)
          : null,
      priority: json['priority'] as String?,
      priorityReasons:
          (json['priority_reasons'] as List<dynamic>?)?.map((e) => e.toString()).toList() ??
              const [],
    );
  }

  bool get isAnomaly => anomalyScore > 0.7;
  bool get isUnknown => classification == 'Unknown';

  Map<String, dynamic> toJson() => {
        'freq': frequency,
        'power': power,
        'bandwidth': bandwidth,
        'time': time.toIso8601String(),
        'type': type,
        'classification': classification,
        'anomaly_score': anomalyScore,
        'spectrum': spectrum,
        'confidence': confidence,
        'analyzer_reason': analyzerReason,
        if (snrDb != null) 'snr_db': snrDb,
        if (modulation != null) 'modulation': modulation,
        if (stability != null) 'stability': stability,
        if (continuity != null) 'continuity': continuity,
        'interference': interference,
        if (noisePct != null) 'noise_pct': noisePct,
        if (quality != null) 'quality': quality,
        if (realProb != null) 'real_prob': realProb,
        if (fpStatus != null) 'fp_status': fpStatus,
        'fp_notes': fpNotes,
        if (seenCount != null) 'seen_count': seenCount,
        if (lastSeenPrior != null)
          'last_seen_prior': lastSeenPrior!.millisecondsSinceEpoch / 1000.0,
        if (candidates.isNotEmpty)
          'candidates': candidates.map((c) => {'label': c.label, 'confidence': c.confidence}).toList(),
        if (confidenceBreakdown.isNotEmpty) 'confidence_breakdown': confidenceBreakdown,
        if (noiseDiagnosis.isNotEmpty) 'noise_diagnosis': noiseDiagnosis,
        if (metrics.isNotEmpty) 'metrics': metrics,
        if (channelInfo != null) 'channel_info': channelInfo,
        if (satellites.isNotEmpty)
          'satellites': satellites
              .map((s) => {'name': s.name, 'sat_type': s.satType, 'confidence': s.confidence})
              .toList(),
        if (useHints.isNotEmpty) 'use_hints': useHints,
        if (bandInfo != null) 'band_info': bandInfo,
        if (priority != null) 'priority': priority,
        if (priorityReasons.isNotEmpty) 'priority_reasons': priorityReasons,
      };
}

/// One ranked classification hypothesis (expert-system top-5 output).
class SignalCandidate {
  final String label;
  final double confidence;

  const SignalCandidate({required this.label, required this.confidence});

  factory SignalCandidate.fromJson(Map<String, dynamic> json) => SignalCandidate(
        label: json['label'] as String? ?? 'Unknown',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      );
}

/// A possible satellite for a satellite-band detection (estimate, never
/// a decoded fact — RTL-SDR power spectra can't identify spacecraft).
class SatelliteGuess {
  final String name;
  final String satType;
  final double confidence;

  const SatelliteGuess({required this.name, required this.satType, required this.confidence});

  factory SatelliteGuess.fromJson(Map<String, dynamic> json) => SatelliteGuess(
        name: json['name'] as String? ?? '?',
        satType: json['sat_type'] as String? ?? '',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      );
}

class SpectrumFrame {
  final List<double> powers;
  final double centerFreq;
  final double sampleRate;
  final DateTime time;

  const SpectrumFrame({
    required this.powers,
    required this.centerFreq,
    required this.sampleRate,
    required this.time,
  });

  factory SpectrumFrame.fromJson(Map<String, dynamic> json) {
    return SpectrumFrame(
      powers: (json['powers'] as List<dynamic>)
          .map((e) => (e as num).toDouble())
          .toList(),
      centerFreq: (json['center_freq'] as num).toDouble(),
      sampleRate: (json['sample_rate'] as num).toDouble(),
      time: DateTime.parse(json['time'] as String),
    );
  }

  double get startFreq => (centerFreq - sampleRate / 2) / 1e6;
  double get endFreq => (centerFreq + sampleRate / 2) / 1e6;
}

enum SignalType {
  fm('FM Radio', '88-108 MHz', '🎵'),
  wifi('WiFi', '2.4/5 GHz', '📶'),
  bluetooth('Bluetooth', '2.4 GHz', '🔵'),
  aviation('Aviation', '118-137 MHz', '✈️'),
  satellite('Satellite', '1.5 GHz', '🛰️'),
  weather('Weather', '162 MHz', '🌦️'),
  unknown('Unknown', '???', '❓'),
  anomaly('Anomaly', '???', '🚨');

  final String label;
  final String freqRange;
  final String emoji;

  const SignalType(this.label, this.freqRange, this.emoji);
}
