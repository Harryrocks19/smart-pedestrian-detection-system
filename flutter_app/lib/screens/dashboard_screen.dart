import 'dart:async';
import 'package:flutter/material.dart';
import '../api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic> _status = {};
  bool _loading = true;
  String _error = '';
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _fetch();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _fetch());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _fetch() async {
    try {
      final s = await ApiService.getStatus();
      setState(() { _status = s; _loading = false; _error = ''; });
    } catch (e) {
      setState(() { _error = 'Cannot connect to server'; _loading = false; });
    }
  }

  Color _signalColor(String s) {
    if (s == 'RED')    return Colors.red;
    if (s == 'YELLOW') return Colors.orange;
    return Colors.green;
  }

  @override
  Widget build(BuildContext context) {
    final signal  = _status['signal']  ?? 'UNKNOWN';
    final people  = _status['people']  ?? 0;
    final alert   = _status['alert']   ?? 'NO';
    final vehicles= _status['vehicles']?? 0;
    final risk    = _status['risk']    ?? 0;
    final viol    = _status['violations'] ?? 0;
    final atype   = _status['alert_type'] ?? '';

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('Smart Pedestrian', style: TextStyle(color: Colors.white)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _fetch,
          )
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error.isNotEmpty
              ? Center(child: Text(_error, style: const TextStyle(color: Colors.red)))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Alert Banner
                      if (alert == 'YES')
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: Colors.red.withOpacity(0.2),
                            border: Border.all(color: Colors.red),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.warning, color: Colors.red),
                              const SizedBox(width: 8),
                              Text('ALERT: $atype',
                                  style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                            ],
                          ),
                        ),

                      // Traffic Signal Widget
                      Center(
                        child: Column(
                          children: [
                            const Text('Traffic Signal', style: TextStyle(color: Colors.white70, fontSize: 13)),
                            const SizedBox(height: 8),
                            Container(
                              width: 60, height: 130,
                              decoration: BoxDecoration(
                                color: const Color(0xFF333333),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                                children: [
                                  _light(Colors.red,    signal == 'RED'),
                                  _light(Colors.orange, signal == 'YELLOW'),
                                  _light(Colors.green,  signal == 'GREEN'),
                                ],
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(signal,
                                style: TextStyle(color: _signalColor(signal),
                                    fontWeight: FontWeight.bold, fontSize: 16)),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      // Stats Grid
                      GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        childAspectRatio: 1.6,
                        children: [
                          _statCard('People',     '$people',  Icons.people,       Colors.blue),
                          _statCard('Vehicles',   '$vehicles',Icons.directions_car,Colors.orange),
                          _statCard('Violations', '$viol',    Icons.warning,      Colors.yellow),
                          _statCard('Risk Events','$risk',    Icons.dangerous,    Colors.red),
                        ],
                      ),

                      const SizedBox(height: 16),
                      Text('Last update: ${_status['timestamp'] ?? ''}',
                          style: const TextStyle(color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                ),
    );
  }

  Widget _light(Color color, bool active) => Container(
    width: 36, height: 36,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      color: active ? color : color.withOpacity(0.15),
      boxShadow: active ? [BoxShadow(color: color.withOpacity(0.6), blurRadius: 10)] : [],
    ),
  );

  Widget _statCard(String label, String value, IconData icon, Color color) =>
      Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(value, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.bold)),
                Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
              ],
            ),
          ],
        ),
      );
}
