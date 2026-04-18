import 'package:flutter/material.dart';
import '../api_service.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});
  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  List<String> _lines = [];
  String _generated = '';
  bool _loading = false;

  Future<void> _generate() async {
    setState(() { _loading = true; });
    try {
      final r = await ApiService.getReport();
      setState(() {
        _lines     = List<String>.from(r['lines'] ?? []);
        _generated = r['generated'] ?? '';
        _loading   = false;
      });
    } catch (_) {
      setState(() {
        _lines   = ['Could not connect to server.'];
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFF0D1117),
    appBar: AppBar(
      backgroundColor: const Color(0xFF161B22),
      title: const Text('AI Report', style: TextStyle(color: Colors.white)),
    ),
    body: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF238636),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _loading ? null : _generate,
              icon: const Icon(Icons.auto_awesome, color: Colors.white),
              label: Text(_loading ? 'Generating...' : 'Generate AI Report',
                  style: const TextStyle(color: Colors.white, fontSize: 15)),
            ),
          ),
          if (_generated.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Generated: $_generated', style: const TextStyle(color: Colors.white38, fontSize: 11)),
          ],
          const SizedBox(height: 16),
          Expanded(
            child: _lines.isEmpty
                ? const Center(child: Text('Tap the button to generate report',
                    style: TextStyle(color: Colors.white38)))
                : ListView.builder(
                    itemCount: _lines.length,
                    itemBuilder: (_, i) {
                      final line = _lines[i];
                      if (line.startsWith('---')) {
                        return const Divider(color: Colors.white24, height: 24);
                      }
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('• ', style: TextStyle(color: Colors.blue, fontSize: 16)),
                            Expanded(child: Text(line, style: const TextStyle(color: Colors.white70, fontSize: 13))),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    ),
  );
}
