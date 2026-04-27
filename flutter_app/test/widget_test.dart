// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:smart_pedestrian_app/main.dart';

void main() {
  testWidgets('Smart Pedestrian App launches', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const SmartPedestrianApp());

    // Verify app loads
    expect(find.byType(SmartPedestrianApp), findsOneWidget);

    // Verify main navigation is present
    expect(find.byType(MainNav), findsOneWidget);

    // Verify bottom navigation bar exists
    expect(find.byType(BottomNavigationBar), findsOneWidget);
  });
}
