"""
core/sensors.py — IoT / sensor feed module (stub).
Ready to accept data from Raspberry Pi, phone sensors, or smart home devices.
"""
from datetime import datetime
from core.logger import logger


class SensorHub:
    """
    Collects and stores sensor data from external IoT devices.
    Data is pushed in via the REST API endpoint and stored in-memory.
    Agents can query the latest readings for contextual awareness.
    """

    def __init__(self):
        self.readings = {}  # { sensor_name: [{ value, unit, timestamp }, ...] }
        self.max_history = 100  # Keep last 100 readings per sensor
        logger.info("SensorHub initialized (IoT stub ready)")

    def push_reading(self, sensor_name: str, value: float, unit: str = "") -> dict:
        """
        Push a new sensor reading.
        
        Args:
            sensor_name: e.g. 'room_temp', 'humidity', 'location', 'power_usage'
            value: The numeric reading
            unit: e.g. '°C', '%', 'W'
        """
        if sensor_name not in self.readings:
            self.readings[sensor_name] = []

        reading = {
            "value": value,
            "unit": unit,
            "timestamp": datetime.now().isoformat()
        }

        self.readings[sensor_name].append(reading)

        # Trim history
        if len(self.readings[sensor_name]) > self.max_history:
            self.readings[sensor_name] = self.readings[sensor_name][-self.max_history:]

        logger.info(f"Sensor '{sensor_name}': {value} {unit}")
        return {"status": "ok", "sensor": sensor_name, "reading": reading}

    def get_latest(self, sensor_name: str) -> dict:
        """Get the most recent reading for a sensor."""
        if sensor_name not in self.readings or not self.readings[sensor_name]:
            return {"status": "no_data", "sensor": sensor_name}
        return {"status": "ok", "sensor": sensor_name, "reading": self.readings[sensor_name][-1]}

    def get_all_latest(self) -> dict:
        """Get the latest reading from every registered sensor."""
        result = {}
        for name, history in self.readings.items():
            if history:
                result[name] = history[-1]
        return result

    def get_sensor_history(self, sensor_name: str, limit: int = 20) -> list:
        """Get historical readings for a sensor."""
        if sensor_name not in self.readings:
            return []
        return self.readings[sensor_name][-limit:]

    def list_sensors(self) -> list:
        """List all registered sensor names."""
        return list(self.readings.keys())


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_sensor_hub() -> SensorHub:
    global _instance
    if _instance is None:
        _instance = SensorHub()
    return _instance
