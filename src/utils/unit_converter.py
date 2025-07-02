import pint

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

    def convert_to_variants(self, value, unit):
        if unit in pixel_units:
            return {"px": value}

        try:
            x: pint.Quantity = self.ureg.Quantity(value=value, units=unit)
        except pint.errors.OffsetUnitCalculusError as e:
            return {unit: value}
        except pint.errors.UndefinedUnitError as e:
            if "m2" in unit or "m3" in unit:
                return self.convert_to_variants(value, unit.replace("m2", "m**2").replace("m3", "m**3"))
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
        return result
