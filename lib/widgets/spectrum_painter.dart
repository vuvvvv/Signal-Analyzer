import 'dart:math';
import 'package:flutter/material.dart';
import '../models/signal_data.dart';

class SpectrumPainter extends CustomPainter {
  final SpectrumFrame? frame;
  final List<double> fallback;
  final double minDb;
  final double maxDb;

  SpectrumPainter({
    this.frame,
    this.fallback = const [],
    this.minDb = -100,
    this.maxDb = -20,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final powers = frame?.powers ?? fallback;
    if (powers.isEmpty) {
      _drawEmpty(canvas, size);
      return;
    }

    _drawGrid(canvas, size);
    _drawSpectrum(canvas, size, powers);
    _drawFreqLabels(canvas, size);
    _drawDbLabels(canvas, size);
  }

  void _drawEmpty(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.green.withOpacity(0.3);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), paint);
    final tp = TextPainter(
      text: const TextSpan(
        text: 'في انتظار الإشارة...',
        style: TextStyle(color: Colors.green, fontSize: 14),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(
      canvas,
      Offset(size.width / 2 - tp.width / 2, size.height / 2 - tp.height / 2),
    );
  }

  void _drawGrid(Canvas canvas, Size size) {
    final gridPaint = Paint()
      ..color = Colors.green.withOpacity(0.15)
      ..strokeWidth = 0.5;

    for (int i = 0; i <= 10; i++) {
      final x = size.width * i / 10;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (int i = 0; i <= 6; i++) {
      final y = size.height * i / 6;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
  }

  void _drawSpectrum(Canvas canvas, Size size, List<double> powers) {
    final n = powers.length;
    final path = Path();
    final fillPath = Path();

    double x0 = 0;
    double y0 = _dbToY(powers[0], size.height);
    path.moveTo(x0, y0);
    fillPath.moveTo(0, size.height);
    fillPath.lineTo(x0, y0);

    for (int i = 1; i < n; i++) {
      final x = size.width * i / (n - 1);
      final y = _dbToY(powers[i], size.height);
      path.lineTo(x, y);
      fillPath.lineTo(x, y);
    }
    fillPath.lineTo(size.width, size.height);
    fillPath.close();

    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Colors.green.withOpacity(0.4),
          Colors.green.withOpacity(0.05),
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..style = PaintingStyle.fill;

    canvas.drawPath(fillPath, fillPaint);

    final linePaint = Paint()
      ..color = Colors.greenAccent
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    canvas.drawPath(path, linePaint);

    // Peak indicator
    final maxPower = powers.reduce(max);
    final maxIdx = powers.indexOf(maxPower);
    if (maxPower > minDb + 10) {
      final px = size.width * maxIdx / (n - 1);
      final py = _dbToY(maxPower, size.height);
      canvas.drawCircle(
        Offset(px, py),
        4,
        Paint()..color = Colors.redAccent,
      );
    }
  }

  void _drawFreqLabels(Canvas canvas, Size size) {
    if (frame == null) return;
    for (int i = 0; i <= 4; i++) {
      final freq = frame!.startFreq + (frame!.endFreq - frame!.startFreq) * i / 4;
      final tp = TextPainter(
        text: TextSpan(
          text: '${freq.toStringAsFixed(1)}M',
          style: const TextStyle(color: Colors.green, fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width * i / 4, size.height - 14));
    }
  }

  void _drawDbLabels(Canvas canvas, Size size) {
    for (int i = 0; i <= 3; i++) {
      final db = maxDb - (maxDb - minDb) * i / 3;
      final y = size.height * i / 3;
      final tp = TextPainter(
        text: TextSpan(
          text: '${db.toInt()}dB',
          style: const TextStyle(color: Colors.green, fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y));
    }
  }

  double _dbToY(double db, double height) {
    final clamped = db.clamp(minDb, maxDb);
    return height * (1 - (clamped - minDb) / (maxDb - minDb));
  }

  @override
  bool shouldRepaint(SpectrumPainter oldDelegate) =>
      frame != oldDelegate.frame || fallback != oldDelegate.fallback;
}

class WaveformPainter extends CustomPainter {
  final List<double> samples;

  const WaveformPainter({required this.samples});

  @override
  void paint(Canvas canvas, Size size) {
    if (samples.isEmpty) return;

    final paint = Paint()
      ..color = Colors.cyanAccent
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    final path = Path();
    final n = samples.length;
    final mid = size.height / 2;

    for (int i = 0; i < n; i++) {
      final x = size.width * i / (n - 1);
      final y = mid - samples[i] * mid * 0.9;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);

    // Center line
    canvas.drawLine(
      Offset(0, mid),
      Offset(size.width, mid),
      Paint()
        ..color = Colors.cyan.withOpacity(0.2)
        ..strokeWidth = 0.5,
    );
  }

  @override
  bool shouldRepaint(WaveformPainter old) => samples != old.samples;
}
