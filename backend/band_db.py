"""RF band database — freq -> allocation identity (NOT station names).

Table-driven catalogue of radio allocations. Each band carries its name,
frequency range, primary use, the technologies that can legitimately live
inside it, and a short description. `lookup()` returns EVERY band that
covers the frequency (overlaps are real: 2483.5 MHz is both end-of-Wi-Fi
and BLE channel 39 territory), best-fit (narrowest) first — the signal
analyzer's shape/behavior scoring then decides which technology is the
closest match.

Adding a band = appending one tuple. No station names, ever.
"""

from __future__ import annotations

# (name, start_mhz, end_mhz, use, technologies, description)
BANDS: list[tuple[str, float, float, str, list[str], str]] = [
    ("AM Broadcast", 0.522, 1.71, "Broadcast Radio",
     ["AM Mono"], "Medium-wave AM broadcasting"),
    ("HF ISM 13.56", 13.553, 13.567, "Short-range RF",
     ["NFC", "RFID HF"], "Near-field readers and HF RFID"),
    ("CB Radio", 26.965, 27.405, "Personal Radio",
     ["AM Voice", "SSB Voice"], "Citizens Band channels 1-40"),
    ("Cordless Phone 49", 49.0, 50.0, "Consumer Telephony",
     ["Analog FM"], "Legacy analog cordless phones"),
    ("VHF Pager", 76.0, 87.5, "Paging",
     ["POCSAG", "FLEX"], "Legacy VHF paging allocations"),
    ("FM Broadcast", 87.5, 108.0, "Broadcast Radio",
     ["FM Stereo", "FM Mono", "RDS"], "Wideband FM broadcasting"),
    ("Airband", 118.0, 137.0, "Aviation",
     ["AM Voice", "ACARS"], "Air traffic control and airline data"),
    ("Weather Satellite 137", 137.0, 138.0, "Satellite Downlink",
     ["NOAA APT", "Meteor LRPT"], "Polar weather satellite downlinks"),
    ("VHF Military/Sat", 138.0, 144.0, "Government/Satellite",
     ["NFM Voice", "Satcom"], "Military and satellite allocations"),
    ("Amateur VHF (2m)", 144.0, 148.0, "Amateur Radio",
     ["NFM Voice", "APRS", "SSB", "CW"], "2-meter ham band; APRS at 144.39"),
    ("VHF Pager/Utility", 148.0, 156.0, "Paging/Business",
     ["POCSAG", "NFM Voice"], "Pagers and business radio"),
    ("Marine VHF", 156.0, 162.4, "Maritime",
     ["NFM Voice", "AIS", "DSC"], "Ship/coast voice and AIS at 161.975/162.025"),
    ("NOAA Weather", 162.4, 162.55, "Weather Broadcast",
     ["NFM Voice", "SAME Alerts"], "Continuous weather radio broadcast"),
    ("TV Broadcast VHF", 174.0, 230.0, "Broadcast TV",
     ["DVB-T", "ATSC", "DAB"], "VHF television / digital audio broadcast"),
    ("ISM 300/315", 300.0, 316.0, "Short-range Devices",
     ["OOK Remotes", "Key Fobs", "Garage Doors", "Proprietary RF"],
     "Low-power remote controls (region-dependent)"),
    ("TETRA/Emergency 380-400", 380.0, 400.0, "Public Safety",
     ["TETRA"], "Emergency-services trunked radio"),
    ("Radiosonde 400-406", 400.0, 406.0, "Meteorology",
     ["Radiosonde Telemetry"], "Weather-balloon telemetry"),
    ("Amateur UHF (70cm)", 420.0, 450.0, "Amateur Radio",
     ["NFM Voice", "DMR", "SSB", "CW"], "70-centimeter ham band"),
    ("ISM 433 MHz", 433.05, 434.79, "Short-range Devices",
     ["OOK/FSK Remotes", "LoRa", "IoT Telemetry", "Key Fobs", "Proprietary RF"],
     "License-free short-range devices (Region 1)"),
    ("PMR446", 446.0, 446.2, "Personal Radio",
     ["NFM Voice", "dPMR"], "License-free walkie-talkies"),
    ("UHF Business/DMR", 450.0, 470.0, "Business Radio",
     ["DMR", "NFM Voice", "P25"], "Business/professional two-way radio"),
    ("FRS/GMRS", 462.5, 467.8, "Personal Radio",
     ["NFM Voice"], "License-free/licensed walkie-talkies (Americas)"),
    ("TV Broadcast UHF", 470.0, 700.0, "Broadcast TV",
     ["DVB-T", "ATSC"], "UHF television broadcasting"),
    ("LTE 700 (B28)", 758.0, 803.0, "Cellular",
     ["LTE", "5G NR"], "700 MHz cellular downlink"),
    ("LTE 800 (B20)", 791.0, 821.0, "Cellular",
     ["LTE"], "800 MHz cellular downlink (EU)"),
    ("Public Safety 800", 806.0, 824.0, "Public Safety",
     ["P25", "NFM Voice"], "Public-safety trunked radio"),
    ("Cellular 850 Uplink", 824.0, 849.0, "Cellular",
     ["GSM", "UMTS", "LTE"], "850 MHz uplink (phones transmit here)"),
    ("ISM 868 MHz", 863.0, 870.0, "Short-range Devices",
     ["LoRa", "Sigfox", "RFID UHF", "IoT Telemetry", "Proprietary RF"],
     "European license-free IoT band"),
    ("Cellular 850/900 Downlink", 869.0, 894.0, "Cellular",
     ["GSM", "UMTS", "LTE"], "850/900 MHz downlink"),
    ("ISM 915 MHz", 902.0, 928.0, "Short-range Devices",
     ["LoRa", "RFID UHF", "IoT Telemetry", "Proprietary RF"],
     "Americas license-free IoT band"),
    ("GSM 900 Downlink", 925.0, 960.0, "Cellular",
     ["GSM", "UMTS", "LTE"], "900 MHz cellular downlink"),
    ("FLEX Pager 929-932", 929.0, 932.0, "Paging",
     ["FLEX"], "FLEX pager transmitters"),
    ("ADS-B", 1089.5, 1090.5, "Aviation Surveillance",
     ["ADS-B", "Mode S"], "Aircraft transponder squitters at 1090 MHz"),
    ("GNSS L5/E5", 1164.0, 1189.0, "Navigation",
     ["GPS L5", "Galileo E5a"], "Modern GNSS civil signals"),
    ("GNSS L2", 1215.0, 1240.0, "Navigation",
     ["GPS L2", "GLONASS L2"], "GNSS second frequency"),
    ("Inmarsat L-band", 1525.0, 1559.0, "Satellite Comms",
     ["Inmarsat"], "Geostationary L-band downlinks"),
    ("GNSS L1/E1/B1", 1559.0, 1610.0, "Navigation",
     ["GPS L1", "Galileo E1", "BeiDou B1", "GLONASS L1"],
     "Primary GNSS band; all constellations near 1575.42/1602 MHz"),
    ("Iridium", 1616.0, 1626.5, "Satellite Comms",
     ["Iridium"], "LEO satellite phone up/downlink"),
    ("Cellular 1800", 1710.0, 1880.0, "Cellular",
     ["GSM", "LTE", "5G NR"], "1800 MHz cellular band"),
    ("Cellular 1900", 1850.0, 1990.0, "Cellular",
     ["GSM", "UMTS", "LTE"], "1900 MHz cellular band (Americas)"),
    ("Cellular 2100", 2110.0, 2170.0, "Cellular",
     ["UMTS", "LTE", "5G NR"], "2100 MHz downlink"),
    ("2.4 GHz ISM", 2400.0, 2483.5, "Short-range Devices",
     ["Wi-Fi", "Bluetooth", "Bluetooth LE", "Zigbee", "Thread", "Proprietary RF"],
     "The crowded license-free band — shape/behavior analysis decides"),
    ("2.4 GHz Upper", 2483.5, 2500.0, "Short-range/Satellite",
     ["Bluetooth LE (ch 39 edge)", "Globalstar"], "Upper edge above Wi-Fi"),
    ("LTE 2600 / 5G n41", 2496.0, 2690.0, "Cellular",
     ["LTE", "5G NR"], "2.5-2.7 GHz cellular"),
    ("5G NR n78", 3300.0, 3800.0, "Cellular",
     ["5G NR"], "Primary mid-band 5G"),
    ("5 GHz ISM/U-NII", 5150.0, 5850.0, "Short-range Devices",
     ["Wi-Fi"], "5 GHz Wi-Fi channels 32-177"),
]


# ---------------------------------------------------------------------------
# RF knowledge base — context the AI does NOT classify with, presented to
# the user as general information about the band. Deliberately worded as
# "commonly used by / typical", never as definitive: allocations differ
# between countries and an RTL-SDR cannot confirm a service's identity.
#
# Fields: apps (common applications), devices (typically observed),
# comm_type, modulations (frequently observed), category, environment,
# activity (typical level), priority (Critical/High/Medium/Low),
# regulatory (general, country-neutral note).
# ---------------------------------------------------------------------------

_K = dict  # brevity

KNOWLEDGE: dict[str, dict] = {
    "FM Broadcast": _K(
        apps=["Music/news broadcasting"], devices=["Broadcast transmitters", "Car/home receivers"],
        comm_type="One-way broadcast", modulations=["WFM", "RDS subcarrier"],
        category="Civilian/Broadcast", environment="Outdoor (high-power towers)",
        activity="Continuous", priority="Medium",
        regulatory="Licensed broadcast service in most regions"),
    "AM Broadcast": _K(
        apps=["News/talk broadcasting"], devices=["MW broadcast transmitters"],
        comm_type="One-way broadcast", modulations=["AM"],
        category="Civilian/Broadcast", environment="Outdoor", activity="Continuous",
        priority="Medium", regulatory="Licensed broadcast service"),
    "Airband": _K(
        apps=["Air traffic control", "Tower/ground communication", "Airline operations"],
        devices=["Aircraft radios", "Control towers", "Ground stations"],
        comm_type="Two-way voice (AM)", modulations=["AM", "ACARS data"],
        category="Aviation", environment="Outdoor/airborne", activity="Intermittent (push-to-talk)",
        priority="Critical", regulatory="Protected aviation allocation worldwide; listening rules vary by country"),
    "ADS-B": _K(
        apps=["Aircraft surveillance"], devices=["Aircraft transponders"],
        comm_type="One-way broadcast bursts", modulations=["PPM"],
        category="Aviation", environment="Airborne", activity="Continuous bursts",
        priority="High", regulatory="Globally harmonized at 1090 MHz"),
    "Marine VHF": _K(
        apps=["Ship-to-ship/shore voice", "Port operations", "Distress calling (Ch 16)"],
        devices=["Ships", "Harbors", "Coast stations"],
        comm_type="Two-way voice + AIS data", modulations=["NFM", "GMSK (AIS)"],
        category="Maritime", environment="Outdoor/coastal", activity="Intermittent",
        priority="High", regulatory="International maritime mobile allocation"),
    "NOAA Weather": _K(
        apps=["Continuous weather broadcast", "Hazard alerts"],
        devices=["Government weather transmitters"], comm_type="One-way broadcast",
        modulations=["NFM", "SAME alert tones"], category="Public Safety/Weather",
        environment="Outdoor", activity="Continuous", priority="High",
        regulatory="Region-specific (Americas); other regions use different weather services"),
    "Weather Satellite 137": _K(
        apps=["Polar weather satellite imagery downlink"],
        devices=["NOAA/Meteor satellites"], comm_type="One-way satellite downlink",
        modulations=["APT (FM)", "LRPT (QPSK)"], category="Satellite/Scientific",
        environment="Space-to-ground", activity="Pass-dependent (10-15 min windows)",
        priority="Medium", regulatory="Meteorological-satellite service allocation"),
    "ISM 433 MHz": _K(
        apps=["Remote controls", "Weather stations", "Industrial sensors", "Alarm systems",
              "Telemetry", "Garage door openers", "Key fobs"],
        devices=["Low-power RF devices", "IoT sensors", "Car key fobs"],
        comm_type="Short one-way bursts", modulations=["ASK", "OOK", "FSK", "GFSK", "LoRa CSS"],
        category="Short-range/ISM", environment="Indoor + outdoor short range",
        activity="Very low duty cycle, burst transmission very common",
        priority="Low", regulatory="License-free short-range band (ITU Region 1); limits vary"),
    "ISM 868 MHz": _K(
        apps=["IoT telemetry", "Smart meters", "LoRaWAN", "Alarm systems"],
        devices=["LoRa nodes/gateways", "Smart-home sensors", "RFID readers"],
        comm_type="Burst data (duty-cycle limited)", modulations=["FSK", "LoRa CSS", "GFSK"],
        category="Short-range/ISM", environment="Indoor + outdoor",
        activity="Low duty cycle", priority="Low",
        regulatory="European license-free SRD band with duty-cycle limits"),
    "ISM 915 MHz": _K(
        apps=["IoT telemetry", "LoRaWAN", "UHF RFID", "Industrial monitoring"],
        devices=["LoRa nodes", "RFID readers", "Utility meters"],
        comm_type="Burst data / frequency hopping", modulations=["FSK", "LoRa CSS", "FHSS"],
        category="Short-range/ISM", environment="Indoor + outdoor",
        activity="Low-moderate", priority="Low",
        regulatory="Americas license-free ISM band"),
    "ISM 300/315": _K(
        apps=["Car key fobs", "Garage doors", "Alarm sensors"],
        devices=["Remote controls", "Vehicle remotes"], comm_type="One-shot bursts",
        modulations=["OOK", "ASK"], category="Short-range/ISM",
        environment="Short range", activity="On-demand (button press)", priority="Low",
        regulatory="Region-dependent short-range device band (Americas/Asia)"),
    "2.4 GHz ISM": _K(
        apps=["Wireless networking", "Personal-area networks", "Smart home", "Peripherals"],
        devices=["Routers/phones (Wi-Fi)", "Earbuds/wearables (Bluetooth)",
                 "Smart-home sensors (Zigbee/Thread)", "Mice/keyboards", "Drones/controllers"],
        comm_type="Two-way packet data", modulations=["OFDM", "GFSK", "O-QPSK DSSS", "FHSS"],
        category="Short-range/ISM", environment="Mostly indoor",
        activity="High occupancy, bursty", priority="Low",
        regulatory="Globally license-free; the most crowded band"),
    "5 GHz ISM/U-NII": _K(
        apps=["High-throughput Wi-Fi"], devices=["Routers", "Laptops/phones"],
        comm_type="Two-way packet data", modulations=["OFDM"],
        category="Short-range/ISM", environment="Indoor",
        activity="Bursty, traffic-dependent", priority="Low",
        regulatory="License-free with DFS/radar-protection rules in parts of the band"),
    "GNSS L1/E1/B1": _K(
        apps=["Satellite navigation"], devices=["GPS/Galileo/BeiDou/GLONASS satellites"],
        comm_type="One-way spread-spectrum downlink", modulations=["BPSK", "BOC"],
        category="Satellite/Navigation", environment="Space-to-ground",
        activity="Continuous (below noise floor)", priority="High",
        regulatory="Protected radionavigation-satellite allocation; interference here is serious"),
    "TETRA/Emergency 380-400": _K(
        apps=["Emergency-services trunked radio"], devices=["TETRA base stations", "Handhelds"],
        comm_type="Trunked two-way digital voice/data", modulations=["π/4-DQPSK"],
        category="Public Safety", environment="Outdoor networks",
        activity="Continuous downlink", priority="High",
        regulatory="Public-safety allocation (Europe/MEA); monitoring rules vary by country"),
    "Amateur VHF (2m)": _K(
        apps=["Ham voice/data", "APRS position reports", "Emergency comms practice"],
        devices=["Amateur transceivers", "Repeaters", "APRS trackers"],
        comm_type="Two-way voice/data", modulations=["NFM", "SSB", "AFSK", "CW"],
        category="Amateur", environment="Outdoor + mobile", activity="Intermittent",
        priority="Medium", regulatory="Licensed amateur service worldwide"),
    "Amateur UHF (70cm)": _K(
        apps=["Ham voice/data", "Repeaters", "Digital modes"],
        devices=["Amateur transceivers", "Repeaters"], comm_type="Two-way voice/data",
        modulations=["NFM", "DMR", "SSB", "CW"], category="Amateur",
        environment="Outdoor + mobile", activity="Intermittent", priority="Medium",
        regulatory="Licensed amateur service; shares with ISM 433 in Region 1"),
    "Iridium": _K(
        apps=["Satellite phones", "Global IoT"], devices=["Iridium LEO satellites", "Sat phones"],
        comm_type="Two-way TDMA satellite", modulations=["DE-QPSK"],
        category="Satellite/Comms", environment="Space-to-ground",
        activity="Bursty", priority="Medium", regulatory="Mobile-satellite service allocation"),
    "Inmarsat L-band": _K(
        apps=["Maritime/aero satellite comms"], devices=["Geostationary satellites", "Terminals"],
        comm_type="Two-way satellite", modulations=["BPSK", "QPSK"],
        category="Satellite/Comms", environment="Space-to-ground",
        activity="Continuous carriers", priority="Medium",
        regulatory="Mobile-satellite service allocation"),
}

# Category-based defaults for bands without a dedicated knowledge entry.
_CATEGORY_DEFAULTS: list[tuple[str, dict]] = [
    ("Cellular", _K(category="Cellular", priority="Medium", activity="Continuous downlink",
                    comm_type="Two-way cellular", environment="Outdoor networks",
                    regulatory="Licensed cellular spectrum")),
    ("Broadcast", _K(category="Civilian/Broadcast", priority="Medium", activity="Continuous",
                     comm_type="One-way broadcast", environment="Outdoor",
                     regulatory="Licensed broadcast spectrum")),
    ("Paging", _K(category="Civilian/Paging", priority="Low", activity="Bursty",
                  comm_type="One-way paging", environment="Outdoor",
                  regulatory="Licensed paging allocations")),
    ("Public Safety", _K(category="Public Safety", priority="High", activity="Intermittent",
                         comm_type="Two-way voice", environment="Outdoor",
                         regulatory="Protected public-safety spectrum; rules vary by country")),
    ("Personal Radio", _K(category="Civilian/Personal", priority="Low", activity="Intermittent",
                          comm_type="Two-way voice", environment="Outdoor short range",
                          regulatory="License-free or lightly licensed personal radio")),
    ("Navigation", _K(category="Satellite/Navigation", priority="High",
                      activity="Continuous (below noise)", comm_type="One-way downlink",
                      environment="Space-to-ground", regulatory="Protected radionavigation spectrum")),
    ("Satellite", _K(category="Satellite", priority="Medium", activity="Pass/carrier dependent",
                     comm_type="Satellite link", environment="Space-to-ground",
                     regulatory="Satellite-service allocations")),
    ("Business Radio", _K(category="Industrial/Business", priority="Medium", activity="Intermittent",
                          comm_type="Two-way voice/data", environment="Outdoor",
                          regulatory="Licensed land-mobile spectrum")),
    ("Short-range", _K(category="Short-range/ISM", priority="Low", activity="Bursty",
                       comm_type="Short-range data", environment="Indoor + outdoor",
                       regulatory="License-free short-range devices; limits vary")),
]


def knowledge_for(band: dict) -> dict:
    """Knowledge entry for a band: dedicated record if present, otherwise
    defaults inferred from its `use` field. Always includes hedged
    phrasing keys — nothing here is a definitive claim."""
    k = KNOWLEDGE.get(band["name"])
    if k is None:
        use = band.get("use", "")
        k = _K(category="Civilian", priority="Low", activity="Unknown",
               comm_type="Unknown", environment="Unknown",
               regulatory="Allocation varies by country")
        for needle, defaults in _CATEGORY_DEFAULTS:
            if needle.lower() in use.lower():
                k = dict(defaults)
                break
        k.setdefault("apps", [band.get("use", "Unknown")])
        k.setdefault("devices", [])
        k.setdefault("modulations", [])
    return {
        "commonly_used_by": k.get("apps", []),
        "typical_devices": k.get("devices", []),
        "communication_type": k.get("comm_type", "Unknown"),
        "common_modulations": k.get("modulations", []),
        "category": k.get("category", "Civilian"),
        "environment": k.get("environment", "Unknown"),
        "typical_activity": k.get("activity", "Unknown"),
        "band_priority": k.get("priority", "Low"),
        "regulatory_note": k.get("regulatory", "Allocation varies by country"),
        "disclaimer": "General information — actual allocations and usage vary by country",
    }


def lookup(freq_mhz: float) -> list[dict]:
    """All bands covering this frequency, narrowest (most specific)
    first. Empty list = outside every catalogued allocation."""
    hits = [
        {
            "name": name,
            "start_mhz": lo,
            "end_mhz": hi,
            "use": use,
            "technologies": list(techs),
            "description": desc,
        }
        for name, lo, hi, use, techs, desc in BANDS
        if lo <= freq_mhz <= hi
    ]
    hits.sort(key=lambda b: b["end_mhz"] - b["start_mhz"])
    for b in hits:
        b["knowledge"] = knowledge_for(b)
    return hits
