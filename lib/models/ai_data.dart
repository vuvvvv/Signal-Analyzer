/// One independently scored element of the audio (true multi-label:
/// Speech 83% and Noise 41% can both be present). `seconds` is how much
/// of the analysis window contained this element.
class AudioComponent {
  final String label;
  final double confidence;
  final double seconds;

  const AudioComponent({required this.label, required this.confidence, this.seconds = 0});

  factory AudioComponent.fromJson(Map<String, dynamic> json) => AudioComponent(
        label: json['label'] as String? ?? 'Noise',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
        seconds: (json['seconds'] as num?)?.toDouble() ?? 0.0,
      );
}

/// A temporal pattern detected over the sliding window, e.g.
/// "Periodic Tone — every 0.9 s, ~0.3 s each, ×6".
class AudioPattern {
  final String name;
  final String detail;

  const AudioPattern({required this.name, required this.detail});

  factory AudioPattern.fromJson(Map<String, dynamic> json) => AudioPattern(
        name: json['name'] as String? ?? '',
        detail: json['detail'] as String? ?? '',
      );
}

/// Backend-computed reception quality for the demodulated audio.
class AudioQuality {
  final double clarity; // 0..1
  final bool choppy;
  final double noiseShare; // 0..1
  final String? noiseCause;

  const AudioQuality({
    required this.clarity,
    required this.choppy,
    required this.noiseShare,
    this.noiseCause,
  });

  factory AudioQuality.fromJson(Map<String, dynamic> json) => AudioQuality(
        clarity: (json['clarity'] as num?)?.toDouble() ?? 0.0,
        choppy: json['choppy'] as bool? ?? false,
        noiseShare: (json['noise_share'] as num?)?.toDouble() ?? 0.0,
        noiseCause: json['noise_cause'] as String?,
      );
}

class AudioClassification {
  final String label;
  final double confidence;
  final List<AudioComponent> components;
  final AudioQuality? quality;
  final List<String> reason;
  final DateTime time;

  // V3 temporal-analysis payload.
  final Map<String, double> timeline; // state -> seconds in window
  final List<AudioPattern> patterns;
  final double stereoPilot; // 0..1, 19 kHz FM pilot evidence

  const AudioClassification({
    required this.label,
    required this.confidence,
    this.components = const [],
    this.quality,
    required this.reason,
    required this.time,
    this.timeline = const {},
    this.patterns = const [],
    this.stereoPilot = 0,
  });

  factory AudioClassification.fromJson(Map<String, dynamic> json) {
    return AudioClassification(
      label: json['label'] as String? ?? 'Noise',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      components: (json['components'] as List<dynamic>?)
              ?.map((e) => AudioComponent.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList() ??
          const [],
      quality: json['quality'] is Map
          ? AudioQuality.fromJson(Map<String, dynamic>.from(json['quality'] as Map))
          : null,
      reason: (json['reason'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
      time: json['time'] != null
          ? DateTime.fromMillisecondsSinceEpoch(((json['time'] as num) * 1000).round())
          : DateTime.now(),
      timeline: (json['timeline'] as Map?)?.map(
            (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
          ) ??
          const {},
      patterns: (json['patterns'] as List<dynamic>?)
              ?.map((e) => AudioPattern.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList() ??
          const [],
      stereoPilot: (json['stereo_pilot'] as num?)?.toDouble() ?? 0.0,
    );
  }

  /// Human-readable mixed label from the strongest elements,
  /// e.g. "Speech + Noise" (capped at 3 so it stays readable).
  String get mixedLabel {
    final strong = components.where((c) => c.confidence >= 0.3).take(3).toList();
    return strong.length > 1 ? strong.map((c) => c.label).join(' + ') : label;
  }
}

/// One entry in the AI activity timeline shown on the AI dashboard.
enum AiEventKind { detection, newSignal, unknownSignal, changedSignal, audio, capture, status, rfEvent }

class AiEvent {
  final AiEventKind kind;
  final String message;
  final DateTime time;

  AiEvent(this.kind, this.message) : time = DateTime.now();
}

class CaptureEntry {
  final String folder;
  final double frequency;
  final double power;
  final double bandwidth;
  final String typeLabel;
  final double anomalyScore;
  final DateTime capturedAt;
  final bool hasSpectrumImage;
  final bool hasAudio;

  const CaptureEntry({
    required this.folder,
    required this.frequency,
    required this.power,
    required this.bandwidth,
    required this.typeLabel,
    required this.anomalyScore,
    required this.capturedAt,
    required this.hasSpectrumImage,
    required this.hasAudio,
  });

  factory CaptureEntry.fromJson(Map<String, dynamic> json) {
    return CaptureEntry(
      folder: json['folder'] as String? ?? '',
      frequency: (json['freq'] as num?)?.toDouble() ?? 0.0,
      power: (json['power'] as num?)?.toDouble() ?? 0.0,
      bandwidth: (json['bandwidth'] as num?)?.toDouble() ?? 0.0,
      typeLabel: json['type_label'] as String? ?? 'Unknown',
      anomalyScore: (json['anomaly_score'] as num?)?.toDouble() ?? 0.0,
      capturedAt: json['captured_at'] != null
          ? DateTime.parse(json['captured_at'] as String)
          : DateTime.now(),
      hasSpectrumImage: json['has_spectrum_image'] as bool? ?? false,
      hasAudio: json['has_audio'] as bool? ?? false,
    );
  }
}
