import 'package:flutter/material.dart';
import '../api_service.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<dynamic> _alerts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    try {
      final a = await ApiService.getAlerts();
      setState(() { _alerts = a.reversed.toList(); _loading = false; });
    } catch (_) {
      setState(() { _loading = false; });
    }
  }

  Color _typeColor(String t) {
    if (t == 'CROWD')          return Colors.red;
    if (t == 'ZONE_BREACH')    return Colors.purple;
    if (t == 'COLLISION_RISK') return Colors.orange;
    return Colors.grey;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFF0D1117),
    appBar: AppBar(
      backgroundColor: const Color(0xFF161B22),
      title: const Text('Alert Log', style: TextStyle(color: Colors.white)),
      actions: [
        IconButton(icon: const Icon(Icons.refresh, color: Colors.white), onPressed: _fetch)
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _alerts.isEmpty
            ? const Center(child: Text('No alerts yet', style: TextStyle(color: Colors.white54)))
            : ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: _alerts.length,
                itemBuilder: (_, i) {
                  final a = _alerts[i];
                  final type = a['Type'] ?? '';
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: _typeColor(type).withOpacity(0.4)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: _typeColor(type).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(type, style: TextStyle(color: _typeColor(type), fontSize: 11, fontWeight: FontWeight.bold)),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(a['Timestamp'] ?? '', style: const TextStyle(color: Colors.white70, fontSize: 12)),
                              Text('People: ${a['People']}  Vehicles: ${a['Vehicles']}  Risk: ${a['Risk']}',
                                  style: const TextStyle(color: Colors.white38, fontSize: 11)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
  );
}
