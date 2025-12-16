import pint
import re

units_variants = {
    "m": ["nm", "mm", "cm", "dm", "m", "in"],
    "1 / s": ["Hz", "kHz", "MHz", "GHz"],
    "B": ["bit", "kbit", "Mbit", "Gbit", "B", "kB", "MB", "GB", "TB", "PB"],
    "B / s": ["bit / s", "kbit / s", "Mbit / s", "Gbit / s", "B / s", "kB / s", "MB / s", "GB / s", "TB / s"],
    "g": ["g", "mg", "kg", "t"],
    "W": ["W", "kW", "MW", "GW", "VA", "kVA", "MVA", "GVA"],
    "Wh": ["Wh", "kWh", "MWh", "GWh"],
    "V": ["V", "mV", "kV"],
    "Pa": ["Pa", "kPa", "MPa", "GPa"],
    "m ** 3": ["mm ** 3", "cm ** 3", "m ** 3", "l"],
    "m ** 3 / s": ["Hz * mm ** 3", "Hz * cm ** 3", "Hz * m ** 3", "m ** 3 / h", "m ** 3 / s"],
    "lm": ["lm", "cd"],
    "lm / m ** 2": ["lm / m ** 2", "cd / m ** 2", "lx"],
    "s": ["s", "ms", "us", "ns", "min", "h", "d"],
    "A": ["A", "mA", "uA", "nA"],
    "Ah": ["Ah", "A*s", "mAh"],
    "°C": ["°C", "K", "°F"],

}

bytes_units = ["bit", "kbit", "Mbit", "Gbit", "b", "kb", "Mb", "Gb", "kB", "MB", "GB", "TB", "PB"]
bytes_per_s_units = ["bit/s", "kbit/s", "Mbit/s", "Gbit/s", "b/s", "kb/s", "Mb/s", "Gb/s", "B/s", "kB/s", "MB/s", "GB/s", "TB/s"]
pixel_units = ["px", "pixel", "pixels"]

class UnitConverter:
    def __init__(self):
        self.ureg: pint.UnitRegistry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
        self.preferred = [self.ureg.meters, self.ureg.second, self.ureg.bit, self.ureg.gram, self.ureg.watt,
                          self.ureg.watt_hour, self.ureg.pascal, self.ureg.lumen, self.ureg.percent, self.ureg.ohm,
                          self.ureg.ampere_hour, self.ureg.degree_Celsius]

    def _convert_to_variants(self, value, unit):
        if unit in pixel_units:
            return {"px": value}
        if unit in ["x", "X", "×"]:
            print("xxxxxxxxxxxxxxxxxxxxxx1", value, unit)
            return {"dimensionless": value}
        if unit == "stron":
            return {"stron": value}
        if "m2" in unit:
            unit = unit.replace("m2", "m**2")
        if "m3" in unit:
            unit = unit.replace("m3", "m**3")
        if unit == '"':
            unit = 'in'

        try:
            x: pint.Quantity = self.ureg.Quantity(value=value, units=unit)
        except pint.errors.OffsetUnitCalculusError as e:
            print("xxxxxxxxxxxxxxxxxxxxxx2", value, unit)
            return {unit: value}
        except pint.errors.UndefinedUnitError as e:
            print("xxxxxxxxxxxxxxxxxxxxxx3", value, unit)
            if "m2" in unit or "m3" in unit:
                return self._convert_to_variants(value, unit.replace("m2", "m**2").replace("m3", "m**3"))
            return {unit: value}


        if unit in bytes_units:
            x_preffered = x.to("B")
        elif unit.replace(" ", "") in bytes_per_s_units:
            x_preffered = x.to("B / s")
        else:
            x_preffered = x.to_preferred(self.preferred)
        short_unit = f"{x_preffered.u:~}"
        unit_variants = units_variants.get(short_unit, [])
        if not unit_variants:
            return {unit: value}
        result = {}
        for variant in unit_variants:
            result[variant] = x.to(variant).m

        if "in" in result:
            result['"'] = result["in"]
        return result

    def convert_to_variants(self, value, unit):
        """Obsługuje zakresy (10-20, 10/20/30) i zwraca wyniki {'unit': {'min': ..., 'max': ...}}."""
        # 🔹 Normalizacja jednostek (m2 → m**2)
        if "m2" in unit:
            unit = unit.replace("m2", "m**2")
        if "m3" in unit:
            unit = unit.replace("m3", "m**3")
        if unit == '"':
            unit = 'in'
        # 🔹 Jeśli mamy zakres np. "10-20", "10/20/30", "10-20-30"
        if isinstance(value, str):
            if re.search(r"\d+\s*[xX×]\s*\d+", value):
                return {unit: {"min": value, "max": value}}
            numbers = re.findall(r"[-+]?\d*\.?\d+", value)
            if len(numbers) > 1:
                nums = [float(n) for n in numbers]
                vmin, vmax = min(nums), max(nums)
                return self._convert_range_to_variants(vmin, vmax, unit)
            elif len(numbers) == 1:
                v = float(numbers[0])
                return self._convert_range_to_variants(v, v, unit)

        # 🔹 Jeśli pojedyncza liczba
        try:
            v = float(value)
            return self._convert_range_to_variants(v, v, unit)
        except Exception:
            return {unit: {"min": value, "max": value}}

    def _convert_range_to_variants(self, vmin, vmax, unit):
        """Wykorzystuje Twoją _convert_to_variants do konwersji zakresu."""
        variants_min = self._convert_to_variants(vmin, unit)
        variants_max = self._convert_to_variants(vmax, unit)
        result = {}

        # scal wyniki min/max dla każdej jednostki
        all_units = set(variants_min.keys()) | set(variants_max.keys())
        for u in all_units:
            min_val = variants_min.get(u, vmin)
            max_val = variants_max.get(u, vmax)
            result[u] = {"min": min_val, "max": max_val}

        return result