import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/ai_data.dart';
import '../models/signal_data.dart';
import '../services/sdr_service.dart';
import '../utils/ar_labels.dart';

/// AI dashboard. Pure display screen: every value here comes from the
/// backend (SignalAnalyzer / AudioClassifierWorker / CaptureManager over
/// the WebSocket). No analysis logic lives in this widget.
///
/// Visual identity intentionally matches the rest of the app: black
/// background, greenAccent accents, monospace numerics, thin bordered
/// cards. All animation is lightweight implicit animation
/// (TweenAnimationBuilder / AnimatedSwitcher / AnimatedSize) — no extra
/// packages, cheap enough for live 12 fps data.
class AiScreen extends StatelessWidget {
  const AiScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<SdrService>(
      builder: (context, sdr, _) {
        return SingleChildScrollView(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _StatusBar(sdr: sdr),
              const SizedBox(height: 10),
              _ProfileSelector(sdr: sdr),
              const SizedBox(height: 14),
              _SectionLabel('تحليل الإشارة الحالية'),
              _AnalysisCard(analysis: sdr.latestAnalysis, sdr: sdr),
              const SizedBox(height: 16),
              _SectionLabel('معلومات النطاق الراديوي'),
              _BandCard(analysis: sdr.latestAnalysis, bandStatus: sdr.bandStatus),
              const SizedBox(height: 16),
              _SectionLabel('تحليل الصوت'),
              _AudioCard(sdr: sdr),
              const SizedBox(height: 16),
              _SectionLabel('سجل نشاط الذكاء الاصطناعي'),
              _TimelineCard(events: sdr.aiEvents),
              const SizedBox(height: 16),
              _SectionLabel('تسجيلات الإشارات المجهولة'),
              _CapturesList(sdr: sdr),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 4),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.greenAccent,
          fontSize: 12,
          letterSpacing: 2,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final Color color;
  final Widget child;
  const _Card({required this.color, required this.child});

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        border: Border.all(color: color.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: child,
    );
  }
}

/// Circular gauge with an animated sweep + animated numeric center.
class _Gauge extends StatelessWidget {
  final String label;
  final double value; // 0..1
  final Color color;

  const _Gauge({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    final v = value.clamp(0.0, 1.0);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(end: v),
          duration: const Duration(milliseconds: 600),
          curve: Curves.easeOutCubic,
          builder: (context, animated, _) {
            return SizedBox(
              width: 56,
              height: 56,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 56,
                    height: 56,
                    child: CircularProgressIndicator(
                      value: animated,
                      strokeWidth: 4,
                      backgroundColor: Colors.white12,
                      valueColor: AlwaysStoppedAnimation(color),
                    ),
                  ),
                  Text(
                    '${(animated * 100).round()}%',
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            );
          },
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 9, letterSpacing: 1)),
      ],
    );
  }
}

/// Animated horizontal percentage bar (used for audio components).
class _PercentBar extends StatelessWidget {
  final String label;
  final double value; // 0..1
  final Color color;

  const _PercentBar({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: TweenAnimationBuilder<double>(
                tween: Tween(end: value.clamp(0.0, 1.0)),
                duration: const Duration(milliseconds: 500),
                curve: Curves.easeOutCubic,
                builder: (context, animated, _) => LinearProgressIndicator(
                  value: animated,
                  minHeight: 8,
                  backgroundColor: Colors.white10,
                  valueColor: AlwaysStoppedAnimation(color),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 38,
            child: Text(
              '${(value * 100).round()}%',
              textAlign: TextAlign.right,
              style: TextStyle(color: color, fontSize: 12, fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String text;
  final Color color;
  final IconData? icon;
  const _Chip(this.text, this.color, {this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        border: Border.all(color: color.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 11, color: color),
            const SizedBox(width: 4),
          ],
          Text(text, style: TextStyle(color: color, fontSize: 10, letterSpacing: 0.5)),
        ],
      ),
    );
  }
}

/// Softly pulsing dot — draws attention without being noisy.
class _PulseDot extends StatefulWidget {
  final Color color;
  const _PulseDot({required this.color});

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween(begin: 0.35, end: 1.0).animate(_controller),
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

class _StatusBar extends StatelessWidget {
  final SdrService sdr;
  const _StatusBar({required this.sdr});

  Color get _statusColor {
    switch (sdr.aiStatus) {
      case 'جاهز':
        return sdr.connected ? Colors.greenAccent : Colors.grey;
      case 'تم حفظ بصمة جديدة':
        return Colors.orange;
      case 'المقارنة مع البصمة':
        return Colors.amber;
      default:
        return Colors.greenAccent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _statusColor;
    return _Card(
      color: color,
      child: Row(
        children: [
          _PulseDot(color: color),
          const SizedBox(width: 10),
          const Text('محرك الذكاء الاصطناعي',
              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
          const Spacer(),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SlideTransition(
                position: Tween(begin: const Offset(0, 0.4), end: Offset.zero).animate(anim),
                child: child,
              ),
            ),
            child: Text(
              sdr.connected ? sdr.aiStatus : 'غير متصل',
              key: ValueKey('${sdr.connected}-${sdr.aiStatus}'),
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
                fontFamily: 'monospace',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Adaptive monitoring: one-tap profile that elevates the displayed
/// priority of matching band categories (display-side preference only).
class _ProfileSelector extends StatelessWidget {
  final SdrService sdr;
  const _ProfileSelector({required this.sdr});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          const Text('وضع المراقبة',
              style: TextStyle(color: Colors.grey, fontSize: 9, letterSpacing: 1)),
          const SizedBox(width: 8),
          ...SdrService.monitoringProfiles.map((p) {
            final selected = p == sdr.monitoringProfile;
            return Padding(
              padding: const EdgeInsets.only(right: 6),
              child: InkWell(
                onTap: () => sdr.setMonitoringProfile(p),
                borderRadius: BorderRadius.circular(10),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: selected ? Colors.greenAccent.withOpacity(0.15) : Colors.transparent,
                    border: Border.all(
                        color: selected ? Colors.greenAccent : Colors.white24),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    p,
                    style: TextStyle(
                      color: selected ? Colors.greenAccent : Colors.white54,
                      fontSize: 10,
                      letterSpacing: 0.5,
                      fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                ),
              ),
            );
          }),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Current signal analysis
// ---------------------------------------------------------------------------

class _AnalysisCard extends StatefulWidget {
  final SignalData? analysis;
  final SdrService sdr;
  const _AnalysisCard({required this.analysis, required this.sdr});

  @override
  State<_AnalysisCard> createState() => _AnalysisCardState();
}

class _AnalysisCardState extends State<_AnalysisCard> {
  bool _expanded = false;

  Color get _color {
    final a = widget.analysis;
    if (a == null) return Colors.grey;
    if (a.isAnomaly) return Colors.red;
    if (a.isUnknown) return Colors.orange;
    return Colors.greenAccent;
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.analysis;
    if (a == null) {
      // Never blank: while scanning, show what the pipeline IS doing
      // (stage-1 spectrum stats) instead of an empty card.
      final bs = widget.sdr.bandStatus;
      final scanning = widget.sdr.connected && bs != null;
      return _Card(
        color: scanning ? Colors.greenAccent : Colors.grey,
        child: scanning
            ? Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.greenAccent),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('جارٍ جمع العينات — تحليل الطيف...',
                            style: TextStyle(color: Colors.greenAccent, fontSize: 13)),
                        const SizedBox(height: 4),
                        Text(
                          'التردد ${(bs['freq'] as num?)?.toStringAsFixed(3) ?? '?'} MHz  •  '
                          'أرضية الضوضاء ${(bs['noise_floor_db'] as num?)?.toStringAsFixed(0) ?? '?'} dB  •  '
                          '${((bs['notes'] as List?)?.isNotEmpty ?? false) ? arSentence((bs['notes'] as List).first.toString()) : 'لا توجد إشارة مهمة بعد'}',
                          style: const TextStyle(color: Colors.white70, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                ],
              )
            : Text(
                widget.sdr.connected
                    ? 'بانتظار بيانات الطيف — ابدأ المسح لرؤية تصنيف الذكاء الاصطناعي'
                    : 'غير متصل — اتصل بالراسبيري باي لبدء التحليل',
                style: const TextStyle(color: Colors.grey, fontSize: 13),
              ),
      );
    }
    final color = _color;
    return _Card(
      color: color,
      child: InkWell(
        onTap: () => setState(() => _expanded = !_expanded),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: Text(
                      arType(a.type),
                      key: ValueKey(a.type),
                      style: TextStyle(color: color, fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                _Gauge(label: 'الثقة', value: a.confidence, color: color),
              ],
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (a.priority != null) _priorityChip(a),
                if (a.modulation != null && a.modulation != 'Unknown')
                  _Chip('التضمين ${a.modulation!}', Colors.greenAccent, icon: Icons.waves),
                if (a.continuity != null)
                  _Chip(
                    arContinuity[a.continuity] ?? a.continuity!,
                    a.continuity == 'intermittent' ? Colors.amber : Colors.greenAccent,
                    icon: a.continuity == 'intermittent' ? Icons.blur_linear : Icons.horizontal_rule,
                  ),
                if (a.interference) _Chip('تشويش', Colors.red, icon: Icons.warning_amber),
                if (a.fpStatus != null) _fingerprintChip(a),
                ..._channelChips(a),
              ],
            ),
            const Divider(color: Colors.white24, height: 22),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _stat('التردد', '${a.frequency.toStringAsFixed(3)} MHz'),
                _stat('القدرة', '${a.power.toStringAsFixed(1)} dBm'),
                _stat('عرض النطاق', '${a.bandwidth.toStringAsFixed(0)} kHz'),
                if (a.snrDb != null) _stat('نسبة الإشارة للضوضاء', '${a.snrDb!.toStringAsFixed(0)} dB'),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                if (a.quality != null)
                  _Gauge(label: 'الجودة', value: a.quality!, color: _grade(a.quality!)),
                if (a.stability != null)
                  _Gauge(label: 'الاستقرار', value: a.stability!, color: _grade(a.stability!)),
                if (a.noisePct != null)
                  _Gauge(label: 'الضوضاء', value: a.noisePct!, color: _grade(1 - a.noisePct!)),
                if (a.realProb != null)
                  _Gauge(label: 'إشارة حقيقية', value: a.realProb!, color: _grade(a.realProb!)),
              ],
            ),
            AnimatedSize(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeOut,
              alignment: Alignment.topCenter,
              child: !_expanded
                  ? const SizedBox(width: double.infinity)
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Divider(color: Colors.white24, height: 22),
                        if (a.confidenceBreakdown.isNotEmpty) ...[
                          const Text('تفصيل الثقة',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 6),
                          ..._breakdownEntries(a).map((e) => _PercentBar(
                                label: e.$1,
                                value: e.$2,
                                color: _grade(e.$2),
                              )),
                          const SizedBox(height: 8),
                        ],
                        if (a.candidates.length > 1) ...[
                          const Text('الاحتمالات مرتبة',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 6),
                          ...a.candidates.map((c) => _PercentBar(
                                label: arType(c.label),
                                value: c.confidence,
                                color: c == a.candidates.first ? color : Colors.white38,
                              )),
                          const SizedBox(height: 8),
                        ],
                        if (a.satellites.isNotEmpty) ...[
                          const Text('أقمار صناعية محتملة (تقديري)',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 4),
                          ...a.satellites.take(4).map((s) => Text(
                                '•  ${arSentence(s.name)} — ${arSentence(s.satType)} (${(s.confidence * 100).toInt()}%)',
                                style: const TextStyle(color: Colors.white70, fontSize: 12),
                              )),
                          const SizedBox(height: 8),
                        ],
                        if (a.useHints.isNotEmpty) ...[
                          const Text('قد تكون صادرة من (تقديري)',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: a.useHints
                                .map((h) => _Chip(arHint(h), Colors.greenAccent, icon: Icons.devices_other))
                                .toList(),
                          ),
                          const SizedBox(height: 8),
                        ],
                        if (a.noiseDiagnosis.isNotEmpty) ...[
                          const Text('تشخيص الضوضاء / التشويش',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 4),
                          ...a.noiseDiagnosis.map((d) => Text('•  ${arSentence(d)}',
                              style: const TextStyle(color: Colors.amber, fontSize: 12))),
                          const SizedBox(height: 8),
                        ],
                        if (a.metrics.isNotEmpty) ...[
                          const Text('قياسات متعمقة',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 6),
                          _MetricsGrid(metrics: a.metrics),
                          const SizedBox(height: 8),
                        ],
                        if (a.seenCount != null)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(
                              a.fpStatus == 'new'
                                  ? 'أول مرة تُرصد هذه الإشارة — تم حفظ البصمة.'
                                  : 'رُصدت ${a.seenCount} مرة.'
                                      '${a.lastSeenPrior != null ? '  آخر رصد ${_ago(a.lastSeenPrior!)}.' : ''}',
                              style: const TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                          ),
                        if (a.fpNotes.isNotEmpty) ...[
                          const Text('التغييرات مقارنة بالبصمة',
                              style: TextStyle(color: Colors.amber, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 4),
                          ...a.fpNotes.map((n) => Text('•  ${arSentence(n)}',
                              style: const TextStyle(color: Colors.amber, fontSize: 12))),
                          const SizedBox(height: 8),
                        ],
                        if (a.priorityReasons.isNotEmpty) ...[
                          const Text('تقييم الأولوية',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 4),
                          ...a.priorityReasons.map((r) => Text('•  ${arSentence(r)}',
                              style: const TextStyle(color: Colors.white70, fontSize: 12))),
                          const SizedBox(height: 8),
                        ],
                        if (a.analyzerReason.isNotEmpty) ...[
                          const Text('لماذا اختار الذكاء الاصطناعي هذا التصنيف',
                              style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 4),
                          ...a.analyzerReason.map(
                            (r) => Padding(
                              padding: const EdgeInsets.only(bottom: 2),
                              child: Text('•  ${arSentence(r)}',
                                  style: const TextStyle(color: Colors.white70, fontSize: 12)),
                            ),
                          ),
                        ],
                      ],
                    ),
            ),
            const SizedBox(height: 6),
            Center(
              child: Icon(
                _expanded ? Icons.expand_less : Icons.expand_more,
                color: Colors.white24,
                size: 18,
              ),
            ),
          ],
        ),
      ),
    );
  }

  static const _priorityColors = {
    'Critical': Colors.red,
    'High': Colors.orange,
    'Medium': Colors.amber,
    'Low': Colors.greenAccent,
    'Unknown': Colors.white54,
  };

  static const _priorityArabic = {
    'Critical': 'حرجة',
    'High': 'عالية',
    'Medium': 'متوسطة',
    'Low': 'منخفضة',
    'Unknown': 'غير معروفة',
  };

  Widget _priorityChip(SignalData a) {
    final (level, boosted) = widget.sdr.effectivePriority(a);
    return _Chip(
      'الأولوية: ${_priorityArabic[level] ?? level}${boosted ? ' ↑' : ''}',
      _priorityColors[level] ?? Colors.white54,
      icon: Icons.flag,
    );
  }

  /// Fixed display order for the multi-source confidence report.
  static List<(String, double)> _breakdownEntries(SignalData a) {
    const order = [
      ('classification', 'التصنيف'),
      ('detection', 'الاكتشاف'),
      ('fingerprint_similarity', 'البصمة'),
      ('rf', 'الراديو'),
      ('overall', 'الإجمالي'),
    ];
    return [
      for (final (key, label) in order)
        if (a.confidenceBreakdown.containsKey(key)) (label, a.confidenceBreakdown[key]!),
    ];
  }

  /// Channel identity chips derived by the backend (Wi-Fi channel, BLE
  /// advertising channel, LTE band/EARFCN, ...) — always estimates.
  List<Widget> _channelChips(SignalData a) {
    final info = a.channelInfo;
    if (info == null) return const [];
    final chips = <Widget>[];
    final system = info['system']?.toString();
    if (info['channel'] != null) {
      chips.add(_Chip(
        'قناة ${info['channel']}'
        '${info['channel_kind'] != null ? ' (${arSentence(info['channel_kind'].toString())})' : ''}'
        '${info['channel_width_mhz'] != null ? ' • ${info['channel_width_mhz']} MHz' : ''}',
        Colors.cyan,
        icon: Icons.tag,
      ));
    }
    if (info['band'] != null) {
      chips.add(_Chip('نطاق ${info['band']}', Colors.cyan, icon: Icons.cell_tower));
    }
    if (info['earfcn_est'] != null) {
      chips.add(_Chip('EARFCN ~${info['earfcn_est']}', Colors.cyan));
    }
    if (info['arfcn_est'] != null) {
      chips.add(_Chip('ARFCN ~${info['arfcn_est']}', Colors.cyan));
    }
    if (chips.isEmpty && system != null) {
      chips.add(_Chip(arSentence(system), Colors.cyan, icon: Icons.tag));
    }
    return chips;
  }

  Widget _fingerprintChip(SignalData a) {
    switch (a.fpStatus) {
      case 'new':
        return const _Chip('إشارة جديدة', Colors.orange, icon: Icons.fiber_new);
      case 'changed':
        return const _Chip('تغيّرت', Colors.amber, icon: Icons.change_circle_outlined);
      default:
        return _Chip('معروفة ×${a.seenCount ?? '?'}', Colors.greenAccent, icon: Icons.fingerprint);
    }
  }

  static Color _grade(double v) {
    if (v >= 0.65) return Colors.greenAccent;
    if (v >= 0.35) return Colors.amber;
    return Colors.red;
  }

  static String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inSeconds < 60) return 'قبل ${d.inSeconds} ثانية';
    if (d.inMinutes < 60) return 'قبل ${d.inMinutes} دقيقة';
    if (d.inHours < 24) return 'قبل ${d.inHours} ساعة';
    return 'قبل ${d.inDays} يوم';
  }

  Widget _stat(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 13, fontFamily: 'monospace')),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 9, letterSpacing: 1)),
      ],
    );
  }
}

/// RF band identity card: which allocation the current frequency sits in,
/// its range and possible technologies, plus a live occupancy census —
/// how many distinct signals the analyzer has seen in this band lately,
/// broken down by classified technology. No station names, by design.
class _BandCard extends StatelessWidget {
  final SignalData? analysis;
  final Map<String, dynamic>? bandStatus;
  const _BandCard({required this.analysis, required this.bandStatus});

  @override
  Widget build(BuildContext context) {
    final a = analysis;
    // Stage-1 fallback: with no classified signal, the backend still
    // sends band_status frames — the card is never blank while tuned.
    Map<String, dynamic>? band = a?.bandInfo;
    double? freq = a?.frequency;
    bool idle = false;
    if (band == null && bandStatus?['band_info'] is Map) {
      band = Map<String, dynamic>.from(bandStatus!['band_info'] as Map);
      freq = (bandStatus!['freq'] as num?)?.toDouble();
      idle = true;
    }
    if (band == null) {
      return _Card(
        color: Colors.grey,
        child: Text(
          a != null
              ? '${a.frequency.toStringAsFixed(3)} MHz خارج جميع التخصيصات المسجلة'
              : (bandStatus != null
                  ? 'التردد الحالي خارج جميع التخصيصات المسجلة'
                  : 'جارٍ المسح... — تظهر هوية النطاق مع أول إطار طيف'),
          style: const TextStyle(color: Colors.grey, fontSize: 13),
        ),
      );
    }

    final techs = (band['technologies'] as List?)?.map((e) => e.toString()).toList() ?? const [];
    final allBands = (band['all_bands'] as List?)?.map((e) => e.toString()).toList() ?? const [];
    final occ = band['occupancy'] is Map ? Map<String, dynamic>.from(band['occupancy'] as Map) : null;
    final byTech = occ?['by_technology'] is Map
        ? Map<String, dynamic>.from(occ!['by_technology'] as Map)
        : const <String, dynamic>{};
    final confidence = (band['confidence'] as num?)?.toDouble() ?? 0.0;
    final alternatives = a?.candidates.skip(1).take(3).toList() ?? const [];

    return _Card(
      color: Colors.greenAccent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 300),
                      child: Text(
                        arBand(band['name']?.toString() ?? 'غير معروف'),
                        key: ValueKey(band['name']),
                        style: const TextStyle(
                            color: Colors.greenAccent, fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${freq?.toStringAsFixed(3) ?? '?'} MHz  •  '
                      '${band['start_mhz']} – ${band['end_mhz']} MHz  •  ${arSentence(band['use']?.toString() ?? 'غير معروف')}',
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 12, fontFamily: 'monospace'),
                    ),
                  ],
                ),
              ),
              if (idle)
                const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 40,
                      height: 40,
                      child: CircularProgressIndicator(
                          strokeWidth: 3, color: Colors.white24),
                    ),
                    SizedBox(height: 4),
                    Text('جارٍ المسح...',
                        style: TextStyle(color: Colors.grey, fontSize: 8, letterSpacing: 1)),
                  ],
                )
              else
                _Gauge(label: 'الثقة', value: confidence, color: Colors.greenAccent),
            ],
          ),
          if (!idle && a != null) ...[
            const SizedBox(height: 8),
            Text(
              'التقنية المحتملة: ${arType(a.type)} (${(a.confidence * 100).toInt()}%)'
              '${alternatives.isNotEmpty ? '   —   بدائل: '
                  '${alternatives.map((c) => '${arType(c.label)} ${(c.confidence * 100).toInt()}%').join(', ')}' : ''}',
              style: const TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ],
          if ((band['description'] ?? '').toString().isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(arSentence(band['description'].toString()),
                style: const TextStyle(color: Colors.grey, fontSize: 11)),
          ],
          ..._knowledgeSection(band),
          if (techs.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('التقنيات المحتملة',
                style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: techs
                  .map((t) => _Chip(
                        arTech(t),
                        // Highlight the technology the analyzer actually picked
                        a != null &&
                                (a.type.toLowerCase().contains(t.toLowerCase()) ||
                                    t.toLowerCase().contains(a.type.toLowerCase()))
                            ? Colors.greenAccent
                            : Colors.white54,
                        icon: Icons.settings_input_antenna,
                      ))
                  .toList(),
            ),
          ],
          if (allBands.length > 1) ...[
            const SizedBox(height: 8),
            Text('يقع أيضاً ضمن: ${allBands.skip(1).map(arBand).join('، ')}',
                style: const TextStyle(color: Colors.grey, fontSize: 11)),
          ],
          if (occ != null) ...[
            const Divider(color: Colors.white24, height: 22),
            Row(
              children: [
                const Icon(Icons.stacked_bar_chart, size: 14, color: Colors.cyan),
                const SizedBox(width: 6),
                Text(
                  'إشغال النطاق — آخر ${occ['window_s']} ثانية',
                  style: const TextStyle(color: Colors.cyan, fontSize: 12),
                ),
                const Spacer(),
                Text(
                  occ['utilization_pct'] != null
                      ? '${(occ['utilization_pct'] as num).toStringAsFixed(0)}%'
                      : 'جارٍ الحساب...',
                  style: const TextStyle(
                      color: Colors.cyan, fontSize: 14,
                      fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                ),
              ],
            ),
            if (occ['utilization_pct'] != null) ...[
              const SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: TweenAnimationBuilder<double>(
                  tween: Tween(end: ((occ['utilization_pct'] as num) / 100).clamp(0.0, 1.0).toDouble()),
                  duration: const Duration(milliseconds: 500),
                  builder: (context, v, _) => LinearProgressIndicator(
                    value: v,
                    minHeight: 6,
                    backgroundColor: Colors.white10,
                    valueColor: const AlwaysStoppedAnimation(Colors.cyan),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 18,
              runSpacing: 8,
              children: [
                _occStat('الإشارات', '${occ['signal_count'] ?? 0}'),
                _occStat('مشغول', occ['busy_s'] != null ? '${occ['busy_s']} ث' : 'جارٍ الحساب...'),
                _occStat('خامل', occ['idle_s'] != null ? '${occ['idle_s']} ث' : 'جارٍ الحساب...'),
                _occStat('متوسط الاستقبال',
                    occ['avg_power_db'] != null ? '${occ['avg_power_db']} dB' : 'بيانات غير كافية'),
                _occStat('أقصى قدرة',
                    occ['max_power_db'] != null ? '${occ['max_power_db']} dB' : 'بيانات غير كافية'),
                _occStat('متوسط الضوضاء',
                    occ['avg_noise_db'] != null ? '${occ['avg_noise_db']} dB' : 'جارٍ الحساب...'),
                _occStat('متوسط عرض النطاق',
                    occ['avg_signal_bw_khz'] != null
                        ? '${occ['avg_signal_bw_khz']} kHz'
                        : 'بيانات غير كافية'),
              ],
            ),
            if (byTech.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: byTech.entries
                    .map((e) => _Chip('${arType(e.key)}: ${e.value}', Colors.cyan))
                    .toList(),
              ),
            ],
            const SizedBox(height: 4),
            const Text(
              'الإحصاءات تغطي نافذة الاستقبال الحالية فقط',
              style: TextStyle(color: Colors.white38, fontSize: 9),
            ),
          ],
        ],
      ),
    );
  }

  /// RF knowledge base: general, country-neutral context about the band.
  /// Wording is deliberately hedged ("commonly used by") — allocations
  /// differ between countries and nothing here is a definitive claim.
  List<Widget> _knowledgeSection(Map<String, dynamic> band) {
    if (band['knowledge'] is! Map) return const [];
    final k = Map<String, dynamic>.from(band['knowledge'] as Map);
    List<String> strs(String key) =>
        (k[key] as List?)?.map((e) => e.toString()).toList() ?? const [];
    final apps = strs('commonly_used_by');
    final devices = strs('typical_devices');
    final mods = strs('common_modulations');

    return [
      const SizedBox(height: 10),
      Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          if ((k['category'] ?? '').toString().isNotEmpty)
            _Chip(arSentence(k['category'].toString()), Colors.white54, icon: Icons.category),
          if ((k['band_priority'] ?? '').toString().isNotEmpty)
            _Chip('أولوية النطاق: ${_AnalysisCardState._priorityArabic[k['band_priority']] ?? k['band_priority']}',
                _AnalysisCardState._priorityColors[k['band_priority']] ?? Colors.white54,
                icon: Icons.flag),
          if ((k['typical_activity'] ?? '').toString().isNotEmpty &&
              k['typical_activity'] != 'Unknown')
            _Chip('النشاط: ${arSentence(k['typical_activity'].toString())}', Colors.white54, icon: Icons.timeline),
        ],
      ),
      if (apps.isNotEmpty) ...[
        const SizedBox(height: 8),
        const Text('يُستخدم عادةً من قِبل',
            style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
        const SizedBox(height: 2),
        Text(apps.map(arSentence).join('  •  '), style: const TextStyle(color: Colors.white70, fontSize: 12)),
      ],
      if (devices.isNotEmpty) ...[
        const SizedBox(height: 6),
        const Text('الأجهزة الشائعة',
            style: TextStyle(color: Colors.grey, fontSize: 10, letterSpacing: 1)),
        const SizedBox(height: 2),
        Text(devices.map(arSentence).join('  •  '), style: const TextStyle(color: Colors.white70, fontSize: 12)),
      ],
      if (mods.isNotEmpty) ...[
        const SizedBox(height: 6),
        Text('أنواع التضمين الشائعة: ${mods.map(arTech).join('، ')}',
            style: const TextStyle(color: Colors.grey, fontSize: 11)),
      ],
      if ((k['regulatory_note'] ?? '').toString().isNotEmpty) ...[
        const SizedBox(height: 6),
        Text('تنظيمي: ${arSentence(k['regulatory_note'].toString())}',
            style: const TextStyle(color: Colors.grey, fontSize: 11)),
      ],
      const SizedBox(height: 4),
      Text(
        arSentence(k['disclaimer']?.toString() ??
            'معلومات عامة — التخصيصات الفعلية تختلف من دولة لأخرى'),
        style: const TextStyle(color: Colors.white38, fontSize: 9),
      ),
    ];
  }

  Widget _occStat(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(value,
            style: const TextStyle(color: Colors.white, fontSize: 12, fontFamily: 'monospace')),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 8, letterSpacing: 1)),
      ],
    );
  }
}


/// Compact two-column grid for the deep-metrics report.
class _MetricsGrid extends StatelessWidget {
  final Map<String, dynamic> metrics;
  const _MetricsGrid({required this.metrics});

  static const _labels = {
    'occupied_bw_khz': ('النطاق المشغول', ' kHz'),
    'peak_power_db': ('ذروة القدرة', ' dB'),
    'avg_power_db': ('متوسط القدرة', ' dB'),
    'symbol_rate': ('معدل الرموز', ''),
    'burst_ms': ('الدفقة', ' ms'),
    'pulse_interval_ms': ('فاصل النبضات', ' ms'),
    'duty_cycle': ('دورة التشغيل', ''),
    'freq_drift_khz_s': ('الانحراف', ' kHz/s'),
    'freq_offset_khz': ('الإزاحة', ' kHz'),
    'peak_density': ('كثافة القمم', ''),
    'flat_top': ('قمة مسطحة', ''),
  };

  @override
  Widget build(BuildContext context) {
    final entries = <(String, String)>[];
    for (final e in _labels.entries) {
      final v = metrics[e.key];
      if (v == null) continue;
      var text = v is String ? arSentence(v) : v.toString();
      if (e.key == 'duty_cycle' && v is num) text = '${(v * 100).round()}%';
      entries.add((e.value.$1, '$text${e.key == 'duty_cycle' ? '' : e.value.$2}'));
    }
    return Wrap(
      spacing: 18,
      runSpacing: 8,
      children: entries
          .map((e) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(e.$2,
                      style: const TextStyle(
                          color: Colors.white, fontSize: 12, fontFamily: 'monospace')),
                  Text(e.$1,
                      style: const TextStyle(color: Colors.grey, fontSize: 8, letterSpacing: 1)),
                ],
              ))
          .toList(),
    );
  }
}

// ---------------------------------------------------------------------------
// Audio analysis
// ---------------------------------------------------------------------------

class _AudioCard extends StatelessWidget {
  final SdrService sdr;
  const _AudioCard({required this.sdr});

  static const _componentColors = {
    'Speech': Colors.greenAccent,
    'Music': Colors.lightGreen,
    'Continuous Tone': Colors.amber,
    'Whistle': Colors.amber,
    'DTMF': Colors.orange,
    'CTCSS Subtone': Colors.orange,
    'Pilot Tone 19k': Colors.cyan,
    'Alert Tone': Colors.red,
    'Digital/Data': Colors.cyan,
    'Noise': Colors.grey,
    'Silence': Colors.white38,
  };

  @override
  Widget build(BuildContext context) {
    final audio = sdr.latestAudioClassification;
    return _Card(
      color: Colors.greenAccent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (audio == null)
            const Text(
              'لا يوجد تحليل صوتي بعد — فعّل الصوت لتصنيفه (كلام / موسيقى / ضوضاء / نغمة / رقمي)',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            )
          else ...[
            Row(
              children: [
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: Text(
                      arAudio(audio.mixedLabel),
                      key: ValueKey(audio.mixedLabel),
                      style: const TextStyle(
                          color: Colors.greenAccent, fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                if (audio.quality != null)
                  _Gauge(
                    label: 'الوضوح',
                    value: audio.quality!.clarity,
                    color: _AnalysisCardState._grade(audio.quality!.clarity),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            // True multi-label: every element scored independently over
            // the sliding window (Speech 83% AND Noise 41% can coexist).
            ...(audio.components.isNotEmpty
                    ? audio.components
                    : [AudioComponent(label: audio.label, confidence: audio.confidence)])
                .take(6)
                .map((c) => _PercentBar(
                      label: c.seconds > 0 ? '${arAudio(c.label)} · ${c.seconds}ث' : arAudio(c.label),
                      value: c.confidence,
                      color: _componentColors[c.label] ?? Colors.greenAccent,
                    )),
            if (audio.patterns.isNotEmpty) ...[
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: audio.patterns
                    .map((p) => _Chip('${arSentence(p.name)}: ${arSentence(p.detail)}', Colors.amber, icon: Icons.repeat))
                    .toList(),
              ),
            ],
            if (audio.stereoPilot > 0.5)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: _Chip('نغمة FM ستيريو 19 kHz', Colors.cyan, icon: Icons.radio),
              ),
            if (audio.timeline.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'آخر 10 ثوانٍ:  ${audio.timeline.entries.map((e) => '${arAudio(e.key)} ${e.value}ث').join('  •  ')}',
                style: const TextStyle(color: Colors.grey, fontSize: 11),
              ),
            ],
            if (audio.quality != null) ...[
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  if (audio.quality!.choppy)
                    const _Chip('صوت متقطع', Colors.amber, icon: Icons.graphic_eq),
                  if (audio.quality!.noiseCause != null)
                    _Chip(arSentence(audio.quality!.noiseCause!), Colors.amber, icon: Icons.info_outline),
                ],
              ),
            ],
            if (audio.reason.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...audio.reason.take(4).map(
                    (r) => Text('•  ${arSentence(r)}', style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ),
            ],
          ],
          const Divider(color: Colors.white24, height: 24),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: sdr.sttActive ? sdr.stopSpeechToText : sdr.startSpeechToText,
                  icon: Icon(sdr.sttActive ? Icons.mic_off : Icons.mic, size: 16),
                  label: Text(sdr.sttActive ? 'إيقاف تحويل الكلام إلى نص' : 'تحويل الكلام إلى نص'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: sdr.sttActive ? Colors.red : Colors.greenAccent,
                    side: BorderSide(color: sdr.sttActive ? Colors.red : Colors.greenAccent),
                  ),
                ),
              ),
            ],
          ),
          if (sdr.lastSttText != null && sdr.lastSttText!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('"${sdr.lastSttText}"',
                style: const TextStyle(color: Colors.white, fontSize: 13, fontStyle: FontStyle.italic)),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

class _TimelineCard extends StatelessWidget {
  final List<AiEvent> events;
  const _TimelineCard({required this.events});

  static const _kindStyle = {
    AiEventKind.newSignal: (Icons.fiber_new, Colors.orange),
    AiEventKind.unknownSignal: (Icons.help_outline, Colors.orange),
    AiEventKind.changedSignal: (Icons.change_circle_outlined, Colors.amber),
    AiEventKind.detection: (Icons.podcasts, Colors.red),
    AiEventKind.audio: (Icons.volume_up, Colors.greenAccent),
    AiEventKind.capture: (Icons.save_alt, Colors.orange),
    AiEventKind.status: (Icons.info_outline, Colors.grey),
    AiEventKind.rfEvent: (Icons.bolt, Colors.amber),
  };

  @override
  Widget build(BuildContext context) {
    if (events.isEmpty) {
      return _Card(
        color: Colors.grey,
        child: const Text('لا توجد أحداث ذكاء اصطناعي بعد', style: TextStyle(color: Colors.grey, fontSize: 13)),
      );
    }
    return _Card(
      color: Colors.greenAccent,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 240),
        child: ListView.builder(
          shrinkWrap: true,
          itemCount: events.length,
          itemBuilder: (context, i) {
            final e = events[i];
            final (icon, color) = _kindStyle[e.kind] ?? (Icons.circle, Colors.grey);
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${e.time.hour.toString().padLeft(2, '0')}:'
                    '${e.time.minute.toString().padLeft(2, '0')}:'
                    '${e.time.second.toString().padLeft(2, '0')}',
                    style: TextStyle(
                        color: Colors.grey.shade600, fontSize: 10, fontFamily: 'monospace'),
                  ),
                  const SizedBox(width: 8),
                  Icon(icon, size: 13, color: color),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(e.message,
                        style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Captures
// ---------------------------------------------------------------------------

class _CapturesList extends StatelessWidget {
  final SdrService sdr;
  const _CapturesList({required this.sdr});

  @override
  Widget build(BuildContext context) {
    final captures = sdr.captures;
    if (captures.isEmpty) {
      return _Card(
        color: Colors.orange,
        child: const Text(
          'لم يتم تسجيل أي إشارات غير اعتيادية بعد',
          style: TextStyle(color: Colors.grey, fontSize: 13),
        ),
      );
    }
    return Column(
      children: [
        for (var i = 0; i < captures.length; i++)
          _CaptureTile(
            capture: captures[i],
            baseUrl: sdr.capturesBaseUrl,
            // Only the newest capture gets the attention pulse.
            highlight: i == 0 &&
                DateTime.now().difference(captures[i].capturedAt).inSeconds < 30,
          ),
      ],
    );
  }
}

class _CaptureTile extends StatefulWidget {
  final CaptureEntry capture;
  final String baseUrl;
  final bool highlight;
  const _CaptureTile({required this.capture, required this.baseUrl, this.highlight = false});

  @override
  State<_CaptureTile> createState() => _CaptureTileState();
}

class _CaptureTileState extends State<_CaptureTile> with SingleTickerProviderStateMixin {
  bool _expanded = false;
  AnimationController? _pulse;

  @override
  void initState() {
    super.initState();
    if (widget.highlight) {
      _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
        ..repeat(reverse: true);
      // Stop pulsing after a short attention window.
      Future.delayed(const Duration(seconds: 12), () {
        if (mounted) _pulse?.stop();
      });
    }
  }

  @override
  void dispose() {
    _pulse?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final capture = widget.capture;
    final imageUrl = '${widget.baseUrl}/${capture.folder}/spectrum.png';

    Widget tile = Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.orange.withOpacity(0.06),
        border: Border.all(color: Colors.orange.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(4),
      ),
      padding: const EdgeInsets.all(8),
      child: InkWell(
        onTap: () => setState(() => _expanded = !_expanded),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (capture.hasSpectrumImage)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: Image.network(
                      imageUrl,
                      width: _expanded ? 128 : 64,
                      height: _expanded ? 96 : 48,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => const SizedBox(
                        width: 64,
                        height: 48,
                        child: Icon(Icons.image_not_supported, color: Colors.grey, size: 18),
                      ),
                    ),
                  ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${capture.frequency.toStringAsFixed(3)} MHz — ${arType(capture.typeLabel)}',
                        style: const TextStyle(
                            color: Colors.orange, fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      Text(
                        '${capture.power.toStringAsFixed(1)} dBm  •  ${capture.bandwidth.toStringAsFixed(0)} kHz  •  '
                        'شذوذ ${(capture.anomalyScore * 100).toInt()}%',
                        style: const TextStyle(color: Colors.grey, fontSize: 10),
                      ),
                      Text(
                        capture.capturedAt.toLocal().toString().substring(0, 19),
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 9),
                      ),
                      if (capture.hasAudio)
                        Text(
                          '${widget.baseUrl}/${capture.folder}/audio.wav',
                          style: const TextStyle(color: Colors.greenAccent, fontSize: 9),
                          overflow: TextOverflow.ellipsis,
                        ),
                    ],
                  ),
                ),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more,
                    color: Colors.white24, size: 16),
              ],
            ),
          ],
        ),
      ),
    );

    if (_pulse == null) return tile;
    return FadeTransition(
      opacity: Tween(begin: 0.6, end: 1.0).animate(_pulse!),
      child: tile,
    );
  }
}
