import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const int kDiscoveryPort = 45833;
const String kDiscoveryMagic = 'DRUM_METRONOME_DISCOVER';

void main() {
  runApp(const MetronomeRemoteApp());
}

class MetronomeRemoteApp extends StatelessWidget {
  const MetronomeRemoteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Drum Metronome Remote',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2FA8A1)),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class MetronomeDevice {
  MetronomeDevice({
    required this.name,
    required this.address,
    required this.httpPort,
    required this.bpm,
    required this.running,
  }) : lastSeen = DateTime.now();

  String name;
  final InternetAddress address;
  final int httpPort;
  int bpm;
  bool running;
  DateTime lastSeen;

  String get id => '${address.address}:$httpPort';

  Uri endpoint(String path) {
    return Uri.parse('http://${address.address}:$httpPort$path');
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final Map<String, MetronomeDevice> _devices = {};
  MetronomeDevice? _selected;
  bool _scanning = false;
  bool _statusInFlight = false;
  bool _tempoDragging = false;
  int _tempoValue = 100;
  Timer? _statusTimer;

  @override
  void initState() {
    super.initState();
    _scanForDevices();
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    super.dispose();
  }

  Future<void> _scanForDevices() async {
    if (_scanning) {
      return;
    }
    setState(() {
      _scanning = true;
      _devices.clear();
      _selected = null;
    });

    RawDatagramSocket? socket;
    final payload = utf8.encode(kDiscoveryMagic);
    try {
      socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;
      socket.listen((event) {
        if (event != RawSocketEvent.read) {
          return;
        }
        final datagram = socket?.receive();
        if (datagram == null) {
          return;
        }
        final text = utf8.decode(datagram.data, allowMalformed: true);
        Map<String, dynamic> decoded;
        try {
          decoded = jsonDecode(text) as Map<String, dynamic>;
        } catch (_) {
          return;
        }
        final name = (decoded['name'] ?? 'Drum Metronome').toString();
        final port = _coerceInt(decoded['http_port'], 45834);
        final bpm = _coerceInt(decoded['bpm'], 100);
        final running = decoded['running'] == true;
        final device = MetronomeDevice(
          name: name,
          address: datagram.address,
          httpPort: port,
          bpm: bpm,
          running: running,
        );
        _upsertDevice(device);
      });

      socket.send(payload, InternetAddress('255.255.255.255'), kDiscoveryPort);
      await Future.delayed(const Duration(milliseconds: 600));
      socket.send(payload, InternetAddress('255.255.255.255'), kDiscoveryPort);
      await Future.delayed(const Duration(milliseconds: 800));
    } finally {
      socket?.close();
      if (mounted) {
        setState(() {
          _scanning = false;
        });
      }
    }

    if (_devices.isNotEmpty && _selected == null) {
      _selectDevice(_devices.values.first);
    }
  }

  void _upsertDevice(MetronomeDevice device) {
    final existing = _devices[device.id];
    if (existing != null) {
      existing.name = device.name;
      existing.bpm = device.bpm;
      existing.running = device.running;
      existing.lastSeen = DateTime.now();
    } else {
      _devices[device.id] = device;
    }

    if (!mounted) {
      return;
    }
    setState(() {
      if (_selected?.id == device.id) {
        _selected = _devices[device.id];
        if (_selected != null && !_tempoDragging) {
          _tempoValue = _selected!.bpm;
        }
      }
    });
  }

  void _selectDevice(MetronomeDevice device) {
    setState(() {
      _selected = device;
      _tempoValue = device.bpm;
    });
    _startStatusPolling();
  }

  void _startStatusPolling() {
    _statusTimer?.cancel();
    if (_selected == null) {
      return;
    }
    _statusTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _fetchStatus();
    });
    _fetchStatus();
  }

  Future<void> _fetchStatus() async {
    final device = _selected;
    if (device == null || _statusInFlight) {
      return;
    }
    _statusInFlight = true;
    try {
      final response = await http
          .get(device.endpoint('/status'))
          .timeout(const Duration(seconds: 1));
      if (response.statusCode != 200) {
        return;
      }
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final bpm = _coerceInt(decoded['bpm'], device.bpm);
      final running = decoded['running'] == true;
      final name = (decoded['name'] ?? device.name).toString();
      final updated = MetronomeDevice(
        name: name,
        address: device.address,
        httpPort: device.httpPort,
        bpm: bpm,
        running: running,
      );
      _upsertDevice(updated);
    } catch (_) {
      // Ignore network errors; keep last known state.
    } finally {
      _statusInFlight = false;
    }
  }

  Future<void> _sendStartStop(bool start) async {
    final device = _selected;
    if (device == null) {
      return;
    }
    final path = start ? '/start' : '/stop';
    try {
      await http
          .post(device.endpoint(path))
          .timeout(const Duration(seconds: 1));
    } catch (_) {
      return;
    }
    _fetchStatus();
  }

  Future<void> _sendTempo(int bpm) async {
    final device = _selected;
    if (device == null) {
      return;
    }
    final clamped = bpm.clamp(20, 400);
    try {
      await http
          .post(
            device.endpoint('/tempo'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'bpm': clamped}),
          )
          .timeout(const Duration(seconds: 1));
    } catch (_) {
      return;
    }
    _fetchStatus();
  }

  @override
  Widget build(BuildContext context) {
    final deviceList = _devices.values.toList()
      ..sort((a, b) => a.name.compareTo(b.name));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Drum Metronome Remote'),
        actions: [
          IconButton(
            tooltip: 'Scan',
            icon: _scanning
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            onPressed: _scanning ? null : _scanForDevices,
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Text(
                    'Devices',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _scanning ? null : _scanForDevices,
                    icon: const Icon(Icons.wifi_tethering),
                    label: Text(_scanning ? 'Scanning...' : 'Scan'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: Card(
                  elevation: 1,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: deviceList.isEmpty
                        ? const Center(
                            child: Text('No devices found.'),
                          )
                        : ListView.separated(
                            itemCount: deviceList.length,
                            separatorBuilder: (_, __) => const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final device = deviceList[index];
                              return ListTile(
                                title: Text(device.name),
                                subtitle: Text(
                                  '${device.address.address}:${device.httpPort}  •  ${device.bpm} BPM',
                                ),
                                leading: Icon(
                                  device.running
                                      ? Icons.play_circle_fill
                                      : Icons.pause_circle_filled,
                                  color: device.running
                                      ? Colors.green
                                      : Colors.orange,
                                ),
                                selected: _selected?.id == device.id,
                                onTap: () => _selectDevice(device),
                              );
                            },
                          ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              _buildControlPanel(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildControlPanel() {
    final device = _selected;
    final hasDevice = device != null;
    final running = device?.running ?? false;

    return Card(
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              hasDevice
                  ? '${device!.name}  (${device.address.address})'
                  : 'Select a device to control',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Status: ${running ? 'Running' : 'Stopped'}',
                    style: TextStyle(
                      color: running ? Colors.green : Colors.orange,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: hasDevice
                      ? () => _sendStartStop(!running)
                      : null,
                  icon: Icon(running ? Icons.stop : Icons.play_arrow),
                  label: Text(running ? 'Stop' : 'Start'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Tempo: ${hasDevice ? _tempoValue : '--'} BPM',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Slider(
              value: (_tempoValue).toDouble(),
              min: 20,
              max: 400,
              divisions: 380,
              label: _tempoValue.toString(),
              onChangeStart: hasDevice
                  ? (_) {
                      setState(() {
                        _tempoDragging = true;
                      });
                    }
                  : null,
              onChanged: hasDevice
                  ? (value) {
                      setState(() {
                        _tempoValue = value.round();
                      });
                    }
                  : null,
              onChangeEnd: hasDevice
                  ? (value) {
                      setState(() {
                        _tempoDragging = false;
                      });
                      _sendTempo(value.round());
                    }
                  : null,
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: hasDevice
                      ? () {
                          final next = (_tempoValue - 1).clamp(20, 400);
                          setState(() {
                            _tempoValue = next;
                          });
                          _sendTempo(next);
                        }
                      : null,
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: hasDevice
                      ? () {
                          final next = (_tempoValue + 1).clamp(20, 400);
                          setState(() {
                            _tempoValue = next;
                          });
                          _sendTempo(next);
                        }
                      : null,
                  icon: const Icon(Icons.add_circle_outline),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

int _coerceInt(dynamic value, int fallback) {
  if (value is int) {
    return value;
  }
  if (value is double) {
    return value.round();
  }
  if (value is String) {
    return int.tryParse(value) ?? fallback;
  }
  return fallback;
}
