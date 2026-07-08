import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/signal_data.dart';
import '../services/sdr_service.dart';
import '../widgets/spectrum_painter.dart';

class SpectrumScreen extends StatefulWidget {
  const SpectrumScreen({super.key});

  @override
  State<SpectrumScreen> createState() => _SpectrumScreenState();
}

class _SpectrumScreenState extends State<SpectrumScreen> {
  final _freqController = TextEditingController(text: '100.0');

  static const _presets = [
    ('راديو FM', 98.0),
    ('الطيران', 127.0),
    ('الطقس', 162.0),
    ('433 ميجاهرتز', 433.9),
    ('868 ميجاهرتز', 868.0),
  ];

  @override
  void dispose() {
    _freqController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SdrService>(
      builder: (context, sdr, _) {
        return Column(
          children: [
            _buildFreqBar(sdr),
            _buildPresets(sdr),
            Expanded(
              flex: 5,
              child: _buildSpectrumView(sdr),
            ),
            Expanded(
              flex: 3,
              child: _buildWaveformView(sdr),
            ),
            _buildControls(sdr),
          ],
        );
      },
    );
  }

  Widget _buildFreqBar(SdrService sdr) {
    return Container(
      color: Colors.black,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        children: [
          const Icon(Icons.radio, color: Colors.green, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: _freqController,
              style: const TextStyle(color: Colors.greenAccent, fontSize: 14),
              decoration: const InputDecoration(
                border: InputBorder.none,
                suffixText: 'MHz',
                suffixStyle: TextStyle(color: Colors.green),
                isDense: true,
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
          ),
          TextButton(
            onPressed: sdr.connected
                ? () {
                    final f = double.tryParse(_freqController.text);
                    if (f != null) sdr.setFrequency(f);
                  }
                : null,
            child: const Text('انتقال', style: TextStyle(color: Colors.greenAccent)),
          ),
        ],
      ),
    );
  }

  Widget _buildPresets(SdrService sdr) {
    return SizedBox(
      height: 32,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        children: _presets.map((preset) {
          return Padding(
            padding: const EdgeInsets.only(right: 6),
            child: ActionChip(
              label: Text(preset.$1, style: const TextStyle(fontSize: 11)),
              backgroundColor: Colors.green.withOpacity(0.15),
              labelStyle: const TextStyle(color: Colors.greenAccent),
              onPressed: sdr.connected
                  ? () {
                      _freqController.text = preset.$2.toString();
                      sdr.setFrequency(preset.$2);
                    }
                  : null,
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildSpectrumView(SdrService sdr) {
    return Container(
      margin: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.black,
        border: Border.all(color: Colors.green.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(6),
            child: Row(
              children: [
                const Text(
                  'الطيف الترددي',
                  style: TextStyle(
                    color: Colors.green,
                    fontSize: 10,
                    letterSpacing: 1,
                  ),
                ),
                const Spacer(),
                Text(
                  '${sdr.centerFreq.toStringAsFixed(1)} MHz',
                  style: const TextStyle(color: Colors.greenAccent, fontSize: 10),
                ),
              ],
            ),
          ),
          Expanded(
            child: ValueListenableBuilder<SpectrumFrame?>(
              valueListenable: sdr.spectrumNotifier,
              builder: (_, frame, __) => CustomPaint(
                painter: SpectrumPainter(frame: frame),
                size: Size.infinite,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWaveformView(SdrService sdr) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.black,
        border: Border.all(color: Colors.cyan.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.all(6),
            child: Text(
              'الموجة',
              style: TextStyle(
                color: Colors.cyan,
                fontSize: 10,
                letterSpacing: 1,
              ),
            ),
          ),
          Expanded(
            child: ValueListenableBuilder<List<double>>(
              valueListenable: sdr.waveformNotifier,
              builder: (_, samples, __) => CustomPaint(
                painter: WaveformPainter(samples: samples),
                size: Size.infinite,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(SdrService sdr) {
    return Container(
      color: Colors.black,
      padding: const EdgeInsets.all(8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _controlBtn(
            icon: sdr.isScanning ? Icons.stop : Icons.play_arrow,
            label: sdr.isScanning ? 'إيقاف' : 'مسح',
            color: sdr.isScanning ? Colors.red : Colors.green,
            onTap: sdr.connected
                ? () {
                    if (sdr.isScanning) {
                      sdr.stopScan();
                    } else {
                      final f = double.tryParse(_freqController.text) ?? 100.0;
                      sdr.startScan(centerFreqMhz: f);
                    }
                  }
                : null,
          ),
          _controlBtn(
            icon: sdr.voiceEnabled ? Icons.volume_up : Icons.volume_off,
            label: 'الصوت الناطق',
            color: sdr.voiceEnabled ? Colors.cyan : Colors.grey,
            onTap: () => sdr.setVoiceEnabled(!sdr.voiceEnabled),
          ),
          _controlBtn(
            icon: sdr.audioMuted ? Icons.headset_off : Icons.headset,
            label: 'الصوت',
            color: sdr.audioMuted ? Colors.grey : Colors.greenAccent,
            onTap: () => sdr.setAudioMuted(!sdr.audioMuted),
          ),
        ],
      ),
    );
  }

  Widget _controlBtn({
    required IconData icon,
    required String label,
    required Color color,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Opacity(
        opacity: onTap == null ? 0.3 : 1.0,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(color: color, fontSize: 10, letterSpacing: 1),
            ),
          ],
        ),
      ),
    );
  }
}
