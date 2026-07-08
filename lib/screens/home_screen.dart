import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/sdr_service.dart';
import 'spectrum_screen.dart';
import 'signals_screen.dart';
import 'settings_screen.dart';
import 'ai_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;

  static const _tabs = [
    (Icons.graphic_eq, 'الطيف'),
    (Icons.wifi_tethering, 'الإشارات'),
    (Icons.psychology, 'الذكاء الاصطناعي'),
    (Icons.settings, 'الإعدادات'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: _buildAppBar(),
      body: IndexedStack(
        index: _tab,
        children: const [
          SpectrumScreen(),
          SignalsScreen(),
          AiScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: _buildNavBar(),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: Colors.black,
      title: Row(
        children: [
          const Icon(Icons.radar, color: Colors.greenAccent, size: 20),
          const SizedBox(width: 8),
          const Text(
            'محلل الإشارات',
            style: TextStyle(
              color: Colors.greenAccent,
              fontSize: 16,
              letterSpacing: 1,
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          Consumer<SdrService>(
            builder: (_, sdr, __) => Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: sdr.connected ? Colors.green : Colors.red,
                    boxShadow: sdr.connected
                        ? [BoxShadow(color: Colors.green.withOpacity(0.6), blurRadius: 6)]
                        : null,
                  ),
                ),
                const SizedBox(width: 6),
                if (sdr.isScanning)
                  const _PulsingDot(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavBar() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.black,
        border: Border(
          top: BorderSide(color: Colors.green.withOpacity(0.3)),
        ),
      ),
      child: Row(
        children: List.generate(_tabs.length, (i) {
          final selected = _tab == i;
          final tab = _tabs[i];
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _tab = i),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                color: Colors.transparent,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      tab.$1,
                      color: selected ? Colors.greenAccent : Colors.grey.shade700,
                      size: 20,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      tab.$2,
                      style: TextStyle(
                        color: selected ? Colors.greenAccent : Colors.grey.shade700,
                        fontSize: 9,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

class _PulsingDot extends StatefulWidget {
  const _PulsingDot();

  @override
  State<_PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<_PulsingDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _anim = Tween<double>(begin: 0.3, end: 1.0).animate(_ctrl);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => Opacity(
        opacity: _anim.value,
        child: const Icon(Icons.fiber_manual_record, color: Colors.red, size: 8),
      ),
    );
  }
}
