db_schema = """

Węzły:
- Property_PL: name, value, unit
- Property_EN: name, value, unit
- Property_DE: name, value, unit
- Product: EAN

Każdy produkt ma dodatkowo label określający jego typ (np. 'ABC_XYZ').
Węzeł produktu jest połączony z węzłami Property_PL, Property_EN, Property_DE za pomocą relacji HAS. Szukaj tylko w jednym języku.
Węzeł property ma właściwości name i value, a także opcjonalnie unit. 
Właściwość unit zawiera informację o jednostce miary wartości property.
np. name: 'Waga', value: 100, unit: 'kg'.
Węzeł Product może mieć połączenie z wieloma węzłami Property o takim samym name, przedstawiających wartość w różnych 
jednostkach miary. Równe wartości przedstawione w różnych jednostkach miary są połączeone relacją IS_EQUAL.
np. name: 'Długość', value: 100, unit: 'cm' oraz name: 'Długość', value: 1, unit: 'm'.
Dostępne jednostki:
m, in, nm, mm, cm, dm, g, mg, kg, null, s, ms, us, ns, min, h, d, Wh, kWh, MWh, GWh, Hz * mm ** 3, Hz * cm ** 3, Hz * m ** 3, m ** 3 / h, m ** 3 / s, W, kW, MW, GW, VA, kVA, MVA, GVA, Hz, kHz, MHz, GHz, bit, kbit, Mbit, Gbit, B, kB, MB, GB, TB, PB, RPM, PLN, mmH2O, bit / s, kbit / s, Mbit / s, Gbit / s, B / s, kB / s, MB / s, GB / s, TB / s, lm / m ** 2, cd / m ** 2, lx, mm ** 3, cm ** 3, m ** 3, l, IOPS, lm, cd, °C, K, °F, Ah, A*s, mAh, EUR, AWG, str/min, Pa, kPa, MPa, GPa, dni, Ohm, szt, VAh, stron/min, stron/mies., ark., mmAq, szt., px, obr/min, stron, pages/min, sheets, CFM, TBW, spm, dBV/Pa, pages, son, m/s2, str/mies, arkuszy, str/mies., lanes, x mm, kWh/rok, miesiące, pages/month, Lux, max, lat, IOPs, st, arka, ark
Używaj tylko nazw pól dostępnych dla danego typu produktu.

Relacje:
- HAS: section_name
- IS_EQUAL: Brak właściwości

Indeksy:
- property_de_index labelsOrTypes: ['Property_DE'], properties: ['name', 'value', 'unit']
- property_en_index labelsOrTypes: ['Property_EN'], properties: ['name', 'value', 'unit']
- property_pl_index labelsOrTypes: ['Property_PL'], properties: ['name', 'value', 'unit']

"""