import 'package:flutter/material.dart';
import '../api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _ctrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _ctrl.text = ApiService.baseUrl;
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await ApiService.setBaseUrl(_ctrl.text.trim());
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Server URL saved!'), backgroundColor: Colors.green),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFF0D1117),
    appBar: AppBar(
      backgroundColor: const Color(0xFF161B22),
      title: const Text('Settings', style: TextStyle(color: Colors.white)),
    ),
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('API Server URL', style: TextStyle(color: Colors.white70, fontSize: 14)),
          const SizedBox(height: 8),
          TextField(
            controller: _ctrl,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'http://192.168.1.100:5000',
              hintStyle: const TextStyle(color: Colors.white38),
              filled: true,
              fillColor: const Color(0xFF161B22),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: Colors.white24)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: Colors.white24)),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1F6FEB),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _save,
              child: const Text('Save', style: TextStyle(color: Colors.white, fontSize: 15)),
            ),
          ),
          const SizedBox(height: 24),
          const Divider(color: Colors.white12),
          const SizedBox(height: 12),
          const Text('How to connect:', style: TextStyle(color: Colors.white54, fontSize: 13, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('1. Run: python api_server.py on your PC\n'
              '2. Find your PC IP (ipconfig on Windows)\n'
              '3. Enter: http://<YOUR_PC_IP>:5000\n'
              '4. Make sure phone and PC are on same WiFi',
              style: TextStyle(color: Colors.white38, fontSize: 12, height: 1.8)),
        ],
      ),
    ),
  );
}
