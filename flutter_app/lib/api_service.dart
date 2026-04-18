import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static String _baseUrl = 'http://192.168.1.100:5000'; // default IP

  static Future<void> setBaseUrl(String url) async {
    _baseUrl = url;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_url', url);
  }

  static Future<void> loadSavedUrl() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString('api_url') ?? _baseUrl;
  }

  static String get baseUrl => _baseUrl;

  static Future<Map<String, dynamic>> getStatus() async {
    final res = await http.get(Uri.parse('$_baseUrl/status')).timeout(const Duration(seconds: 5));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getAlerts() async {
    final res = await http.get(Uri.parse('$_baseUrl/alerts')).timeout(const Duration(seconds: 5));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getSignalLog() async {
    final res = await http.get(Uri.parse('$_baseUrl/signal')).timeout(const Duration(seconds: 5));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getSnapshots() async {
    final res = await http.get(Uri.parse('$_baseUrl/snapshots')).timeout(const Duration(seconds: 5));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getReport() async {
    final res = await http.get(Uri.parse('$_baseUrl/report')).timeout(const Duration(seconds: 5));
    return jsonDecode(res.body);
  }

  static String heatmapUrl()  => '$_baseUrl/heatmap';
  static String snapshotUrl(String filename) => '$_baseUrl/snapshot/$filename';
}
