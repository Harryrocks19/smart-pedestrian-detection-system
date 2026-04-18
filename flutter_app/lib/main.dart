import 'package:flutter/material.dart';
import 'api_service.dart';
import 'screens/dashboard_screen.dart';
import 'screens/alerts_screen.dart';
import 'screens/heatmap_screen.dart';
import 'screens/report_screen.dart';
import 'screens/settings_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.loadSavedUrl();
  runApp(const SmartPedestrianApp());
}

class SmartPedestrianApp extends StatelessWidget {
  const SmartPedestrianApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Smart Pedestrian',
    debugShowCheckedModeBanner: false,
    theme: ThemeData.dark().copyWith(
      scaffoldBackgroundColor: const Color(0xFF0D1117),
      colorScheme: const ColorScheme.dark(primary: Color(0xFF1F6FEB)),
    ),
    home: const MainNav(),
  );
}

class MainNav extends StatefulWidget {
  const MainNav({super.key});
  @override
  State<MainNav> createState() => _MainNavState();
}

class _MainNavState extends State<MainNav> {
  int _idx = 0;

  final _screens = const [
    DashboardScreen(),
    AlertsScreen(),
    HeatmapScreen(),
    ReportScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
    body: _screens[_idx],
    bottomNavigationBar: BottomNavigationBar(
      currentIndex: _idx,
      onTap: (i) => setState(() => _idx = i),
      backgroundColor: const Color(0xFF161B22),
      selectedItemColor: const Color(0xFF1F6FEB),
      unselectedItemColor: Colors.white38,
      type: BottomNavigationBarType.fixed,
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard),    label: 'Dashboard'),
        BottomNavigationBarItem(icon: Icon(Icons.warning),      label: 'Alerts'),
        BottomNavigationBarItem(icon: Icon(Icons.thermostat),   label: 'Heatmap'),
        BottomNavigationBarItem(icon: Icon(Icons.analytics),    label: 'Report'),
        BottomNavigationBarItem(icon: Icon(Icons.settings),     label: 'Settings'),
      ],
    ),
  );
}
