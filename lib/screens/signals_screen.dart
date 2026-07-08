import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/signal_data.dart';
import '../services/sdr_service.dart';
import '../utils/ar_labels.dart';

class SignalsScreen extends StatelessWidget {
  const SignalsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<SdrService>(
      builder: (context, sdr, _) {
        final signals = sdr.detectedSignals;

        return Column(
          children: [
            _buildSummary(signals),
            Expanded(
              child: signals.isEmpty
                  ? _buildEmpty()
                  : ListView.builder(
                      itemCount: signals.length,
                      itemBuilder: (ctx, i) => _SignalTile(signal: signals[i]),
                    ),
            ),
            _buildActions(context, sdr),
          ],
        );
      },
    );
  }

  Widget _buildSummary(List<SignalData> signals) {
    final anomalies = signals.where((s) => s.isAnomaly).length;
    final unknown = signals.where((s) => s.isUnknown).length;

    return Container(
      color: Colors.black,
      padding: const EdgeInsets.all(12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _stat('الإجمالي', signals.length.toString(), Colors.green),
          _stat('شاذة', anomalies.toString(), Colors.red),
          _stat('مجهولة', unknown.toString(), Colors.orange),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 22,
            fontWeight: FontWeight.bold,
            fontFamily: 'monospace',
          ),
        ),
        Text(
          label,
          style: TextStyle(color: color.withOpacity(0.7), fontSize: 10, letterSpacing: 1),
        ),
      ],
    );
  }

  Widget _buildEmpty() {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.signal_cellular_nodata, color: Colors.green, size: 48),
          SizedBox(height: 12),
          Text(
            'لم يتم اكتشاف أي إشارات بعد\nابدأ المسح لرؤية الإشارات',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.green, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context, SdrService sdr) {
    return Container(
      color: Colors.black,
      padding: const EdgeInsets.all(8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          TextButton.icon(
            onPressed: sdr.detectedSignals.isEmpty ? null : sdr.clearSignals,
            icon: const Icon(Icons.clear_all, size: 16),
            label: const Text('مسح الكل'),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
          ),
        ],
      ),
    );
  }
}

class _SignalTile extends StatelessWidget {
  final SignalData signal;

  const _SignalTile({required this.signal});

  Color get _classColor {
    if (signal.isAnomaly) return Colors.red;
    if (signal.isUnknown) return Colors.orange;
    return Colors.green;
  }

  String get _typeEmoji {
    final t = signal.type.toLowerCase();
    if (t.contains('fm')) return '🎵';
    if (t.contains('wifi')) return '📶';
    if (t.contains('bluetooth') || t.contains('bt')) return '🔵';
    if (t.contains('aviation') || t.contains('air')) return '✈️';
    if (t.contains('satellite') || t.contains('sat')) return '🛰️';
    if (t.contains('weather')) return '🌦️';
    if (signal.isAnomaly) return '🚨';
    return '📡';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _classColor.withOpacity(0.07),
        border: Border.all(color: _classColor.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: ListTile(
        dense: true,
        leading: Text(_typeEmoji, style: const TextStyle(fontSize: 22)),
        title: Row(
          children: [
            Text(
              '${signal.frequency.toStringAsFixed(2)} MHz',
              style: TextStyle(
                color: _classColor,
                fontFamily: 'monospace',
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: _classColor.withOpacity(0.15),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                arType(signal.type),
                style: TextStyle(color: _classColor, fontSize: 10),
              ),
            ),
          ],
        ),
        subtitle: Text(
          '${signal.power.toStringAsFixed(1)} dBm  •  '
          'عرض النطاق ${signal.bandwidth.toStringAsFixed(0)} kHz  •  '
          '${_timeAgo(signal.time)}',
          style: TextStyle(color: Colors.grey.shade600, fontSize: 10),
        ),
        trailing: signal.isAnomaly
            ? Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.warning, color: Colors.red, size: 16),
                  Text(
                    '${(signal.anomalyScore * 100).toInt()}%',
                    style: const TextStyle(color: Colors.red, fontSize: 9),
                  ),
                ],
              )
            : null,
      ),
    );
  }

  String _timeAgo(DateTime t) {
    final diff = DateTime.now().difference(t);
    if (diff.inSeconds < 60) return 'قبل ${diff.inSeconds} ث';
    if (diff.inMinutes < 60) return 'قبل ${diff.inMinutes} د';
    return 'قبل ${diff.inHours} س';
  }
}
