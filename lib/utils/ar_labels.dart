/// ترجمة عرض فقط للتسميات القادمة من الباك اند.
/// القيم الإنجليزية الأصلية تبقى كما هي داخل المنطق (البصمات، الألوان،
/// الإيموجي...) — هذه الدوال تُستخدم عند العرض فقط، وأي تسمية غير
/// معروفة تُعرض بنصها الأصلي.
library;

const _signalTypes = <String, String>{
  'Unknown': 'مجهول',
  'Anomaly': 'شذوذ',
  'FM Broadcast': 'بث إذاعي FM',
  'FM Radio': 'راديو FM',
  'AM Broadcast': 'بث إذاعي AM',
  'AM Radio': 'راديو AM',
  'Airband Voice': 'اتصالات الطيران الصوتية',
  'Airband (Aviation)': 'نطاق الطيران',
  'ACARS': 'ACARS (رسائل طائرات)',
  'ADS-B': 'ADS-B (تتبع طائرات)',
  'ADS-B Aircraft': 'ADS-B (تتبع طائرات)',
  'NOAA Weather Radio': 'راديو الطقس NOAA',
  'NOAA APT Satellite': 'قمر الطقس NOAA APT',
  'Meteor LRPT Satellite': 'قمر ميتيور LRPT',
  'GPS L1': 'GPS L1',
  'GPS L2': 'GPS L2',
  'Galileo E1': 'جاليليو E1',
  'GLONASS L1': 'جلوناس L1',
  'BeiDou B1': 'بيدو B1',
  'Inmarsat': 'إنمارسات',
  'Iridium': 'إيريديوم',
  'APRS': 'APRS (تتبع لاسلكي)',
  'AIS': 'AIS (تتبع سفن)',
  'POCSAG Pager': 'جهاز نداء POCSAG',
  'FLEX Pager': 'جهاز نداء FLEX',
  'Walkie-Talkie': 'جهاز لاسلكي يدوي',
  'DMR': 'راديو رقمي DMR',
  'DMR/Business Radio': 'راديو أعمال DMR',
  'TETRA': 'تيترا TETRA',
  'P25': 'راديو P25',
  'CB Radio': 'راديو CB',
  'Cordless Phone': 'هاتف لاسلكي منزلي',
  'Bluetooth Classic': 'بلوتوث كلاسيكي',
  'Bluetooth LE': 'بلوتوث منخفض الطاقة',
  'Zigbee/Thread': 'زيجبي/ثريد',
  'Wi-Fi': 'واي فاي',
  'WiFi': 'واي فاي',
  'LoRa': 'لورا LoRa',
  'Remote Control/Key Fob': 'جهاز تحكم / مفتاح عن بُعد',
  'RFID Reader': 'قارئ RFID',
  'NFC 13.56': 'NFC 13.56',
  'GSM': 'شبكة GSM',
  'GSM 900': 'شبكة GSM 900',
  'UMTS': 'شبكة UMTS (3G)',
  'LTE': 'شبكة LTE (4G)',
  '5G NR': 'شبكة 5G',
  'Amateur VHF': 'هواة VHF',
  'Amateur UHF': 'هواة UHF',
};

/// يترجم نوع الإشارة، ويعالج نمط "Unknown X Device" القادم من المحلل.
String arType(String type) {
  final direct = _signalTypes[type];
  if (direct != null) return direct;
  if (type.startsWith('Unknown') && type.endsWith('Device')) {
    final middle = type
        .replaceFirst('Unknown', '')
        .replaceFirst('Device', '')
        .trim();
    return middle.isEmpty ? 'جهاز مجهول' : 'جهاز مجهول ($middle)';
  }
  return type;
}

const _audioLabels = <String, String>{
  // مفاتيح خط الزمن (يرسلها الباك اند بأحرف صغيرة)
  'speech': 'كلام',
  'music': 'موسيقى',
  'noise': 'ضوضاء',
  'silence': 'صمت',
  'data': 'بيانات',
  'tone': 'نغمة',
  'Speech': 'كلام',
  'Music': 'موسيقى',
  'Noise': 'ضوضاء',
  'Silence': 'صمت',
  'Digital/Data': 'رقمي/بيانات',
  'Continuous Tone': 'نغمة مستمرة',
  'Whistle': 'صفير',
  'DTMF': 'نغمات DTMF',
  'CTCSS Subtone': 'نغمة CTCSS فرعية',
  'Pilot Tone 19k': 'نغمة توجيه 19k',
  'Alert Tone': 'نغمة تنبيه',
};

/// يترجم تسمية صوتية واحدة أو تسمية مركّبة مثل "Speech + Noise".
String arAudio(String label) {
  final direct = _audioLabels[label];
  if (direct != null) return direct;
  if (label.contains('+')) {
    return label
        .split('+')
        .map((p) => _audioLabels[p.trim()] ?? p.trim())
        .join(' + ');
  }
  return label;
}

const _useHints = <String, String>{
  'Audio headset/speaker': 'سماعة/مكبر صوت',
  'Car hands-free': 'نظام سيارة بدون يدين',
  'Wireless controller': 'يد تحكم لاسلكية',
  'Smartwatch/fitness band': 'ساعة ذكية/سوار لياقة',
  'Wireless earbuds': 'سماعات أذن لاسلكية',
  'IoT sensor/beacon': 'حساس/منارة إنترنت الأشياء',
  'Computer peripheral (mouse/keyboard)': 'ملحق حاسوب (فأرة/لوحة مفاتيح)',
  'Medical device': 'جهاز طبي',
  'Smart-home sensor': 'حساس منزل ذكي',
  'Smart bulb/switch': 'لمبة/مفتاح ذكي',
  'Thermostat/hub': 'منظم حرارة/موزع ذكي',
  'IoT telemetry node': 'عقدة قياس عن بُعد',
  'Smart meter': 'عداد ذكي',
  'GPS tracker': 'متتبع GPS',
  'Car key fob': 'مفتاح سيارة عن بُعد',
  'Garage door opener': 'فاتح باب الكراج',
  'Alarm/doorbell sensor': 'حساس إنذار/جرس باب',
  'Router/access point': 'راوتر/نقطة وصول',
  'Phone/laptop traffic': 'بيانات هاتف/لابتوب',
  'Camera/streaming device': 'كاميرا/جهاز بث',
  'Access-control gate': 'بوابة تحكم بالدخول',
  'Inventory scanner': 'ماسح مخزون',
};

String arHint(String hint) => _useHints[hint] ?? hint;

// ---------------------------------------------------------------------------
// قاعدة بيانات النطاقات (band_db.py): أسماء النطاقات والتقنيات — عرض فقط.
// ---------------------------------------------------------------------------

const _bandNames = <String, String>{
  'AM Broadcast': 'البث الإذاعي AM',
  'HF ISM 13.56': 'ISM ‏13.56 ميجاهرتز HF',
  'CB Radio': 'راديو CB',
  'Cordless Phone 49': 'هواتف لاسلكية 49 ميجاهرتز',
  'VHF Pager': 'أجهزة نداء VHF',
  'FM Broadcast': 'البث الإذاعي FM',
  'Airband': 'نطاق الطيران',
  'Weather Satellite 137': 'أقمار الطقس 137 ميجاهرتز',
  'VHF Military/Sat': 'عسكري/أقمار VHF',
  'Amateur VHF (2m)': 'هواة VHF ‏(2 متر)',
  'VHF Pager/Utility': 'نداء/خدمات VHF',
  'Marine VHF': 'البحري VHF',
  'NOAA Weather': 'طقس NOAA',
  'TV Broadcast VHF': 'بث تلفزيوني VHF',
  'ISM 300/315': 'ISM ‏300/315 ميجاهرتز',
  'TETRA/Emergency 380-400': 'تيترا/طوارئ 380-400',
  'Radiosonde 400-406': 'مسابير الطقس 400-406',
  'Amateur UHF (70cm)': 'هواة UHF ‏(70 سم)',
  'ISM 433 MHz': 'ISM ‏433 ميجاهرتز',
  'PMR446': 'لاسلكي شخصي PMR446',
  'UHF Business/DMR': 'أعمال UHF/DMR',
  'FRS/GMRS': 'لاسلكي شخصي FRS/GMRS',
  'TV Broadcast UHF': 'بث تلفزيوني UHF',
  'LTE 700 (B28)': 'LTE ‏700 ‏(B28)',
  'LTE 800 (B20)': 'LTE ‏800 ‏(B20)',
  'Public Safety 800': 'سلامة عامة 800',
  'Cellular 850 Uplink': 'خلوي 850 صاعد',
  'ISM 868 MHz': 'ISM ‏868 ميجاهرتز',
  'Cellular 850/900 Downlink': 'خلوي 850/900 هابط',
  'ISM 915 MHz': 'ISM ‏915 ميجاهرتز',
  'GSM 900 Downlink': 'GSM ‏900 هابط',
  'FLEX Pager 929-932': 'نداء FLEX ‏929-932',
  'ADS-B': 'ADS-B (تتبع طائرات)',
  'GNSS L5/E5': 'ملاحة GNSS L5/E5',
  'GNSS L2': 'ملاحة GNSS L2',
  'Inmarsat L-band': 'إنمارسات نطاق L',
  'GNSS L1/E1/B1': 'ملاحة GNSS L1/E1/B1',
  'Iridium': 'إيريديوم',
  'Cellular 1800': 'خلوي 1800',
  'Cellular 1900': 'خلوي 1900',
  'Cellular 2100': 'خلوي 2100',
  '2.4 GHz ISM': 'ISM ‏2.4 جيجاهرتز',
  '2.4 GHz Upper': 'أعلى 2.4 جيجاهرتز',
  'LTE 2600 / 5G n41': 'LTE ‏2600 / 5G n41',
  '5G NR n78': '5G NR نطاق n78',
  '5 GHz ISM/U-NII': 'ISM/U-NII ‏5 جيجاهرتز',
  // الأسماء الاحتياطية (KNOWN_BANDS في المحلل)
  'BLE/Zigbee Upper': 'أعلى BLE/زيجبي',
  'GNSS L1 Band': 'نطاق ملاحة GNSS L1',
  'GNSS L5': 'ملاحة GNSS L5',
  'GSM/LTE 1800': 'GSM/LTE ‏1800',
  'GSM/UMTS Downlink': 'GSM/UMTS هابط',
  'GSM/UMTS Uplink': 'GSM/UMTS صاعد',
  'ISM 433 (Remote/IoT)': 'ISM ‏433 (تحكم/IoT)',
  'ISM 868 (LoRa/RFID)': 'ISM ‏868 ‏(LoRa/RFID)',
  'ISM 915 (LoRa/RFID)': 'ISM ‏915 ‏(LoRa/RFID)',
  'LTE Band 2/25': 'LTE نطاق 2/25',
  'LTE Band 20': 'LTE نطاق 20',
  'LTE Band 28': 'LTE نطاق 28',
  'LTE Band 7 / 5G n41': 'LTE نطاق 7 / 5G n41',
  'POCSAG/Pager VHF': 'نداء POCSAG على VHF',
  'Pager': 'أجهزة نداء',
  'Public Safety': 'سلامة عامة',
  'Radiosonde/Meteo': 'مسابير طقس/أرصاد',
  'Satellite/Military': 'ساتلي/عسكري',
  'TETRA/Emergency': 'تيترا/طوارئ',
  'TV Broadcast (UHF)': 'بث تلفزيوني (UHF)',
  'TV Broadcast (VHF)': 'بث تلفزيوني (VHF)',
  'UMTS/LTE 2100': 'UMTS/LTE ‏2100',
  'Walkie-Talkie (FRS/GMRS)': 'لاسلكي يدوي (FRS/GMRS)',
  'Walkie-Talkie (PMR446)': 'لاسلكي يدوي (PMR446)',
  'Weather Satellite': 'أقمار الطقس',
  'WiFi 5GHz': 'واي فاي 5 جيجاهرتز',
  'WiFi/Bluetooth 2.4GHz': 'واي فاي/بلوتوث 2.4 جيجاهرتز',
  'Airband (Aviation)': 'نطاق الطيران',
  'Cordless Phone': 'هواتف لاسلكية منزلية',
  'NOAA Weather Radio': 'راديو الطقس NOAA',
};

/// قيم استمرارية الإشارة (activity pattern في المحلل).
const arContinuity = <String, String>{
  'continuous': 'مستمرة',
  'intermittent': 'متقطعة',
  'periodic': 'دورية',
  'pulsed': 'نبضية',
  'on-demand': 'عند الطلب',
};

/// اسم النطاق: قاموس النطاقات أولاً ثم أنواع الإشارات ثم الأصل.
String arBand(String name) => _bandNames[name] ?? arType(name);

const _techNames = <String, String>{
  'AM Mono': 'AM أحادي',
  'AM Voice': 'صوت AM',
  'SSB Voice': 'صوت SSB',
  'Analog FM': 'FM تناظري',
  'FM Stereo': 'FM ستيريو',
  'FM Mono': 'FM أحادي',
  'NFM Voice': 'صوت NFM',
  'Satcom': 'اتصالات ساتلية',
  'SAME Alerts': 'تنبيهات SAME',
  'OOK Remotes': 'أجهزة تحكم OOK',
  'OOK/FSK Remotes': 'أجهزة تحكم OOK/FSK',
  'Key Fobs': 'مفاتيح عن بُعد',
  'Garage Doors': 'أبواب كراجات',
  'Proprietary RF': 'إرسال RF خاص',
  'IoT Telemetry': 'قياس IoT عن بُعد',
  'Radiosonde Telemetry': 'قياس مسبار الطقس',
  'Bluetooth': 'بلوتوث',
  'Bluetooth LE': 'بلوتوث منخفض الطاقة',
  'Bluetooth LE (ch 39 edge)': 'بلوتوث LE (حافة قناة 39)',
  'Zigbee': 'زيجبي',
  'Thread': 'ثريد',
  'Wi-Fi': 'واي فاي',
  'LoRa': 'لورا LoRa',
  'Sigfox': 'سيجفوكس',
  'Globalstar': 'جلوبال ستار',
  'Inmarsat': 'إنمارسات',
  'Iridium': 'إيريديوم',
  'Mode S': 'نمط Mode S',
  'Galileo E1': 'جاليليو E1',
  'Galileo E5a': 'جاليليو E5a',
  'BeiDou B1': 'بيدو B1',
  'GLONASS L1': 'جلوناس L1',
  'GLONASS L2': 'جلوناس L2',
};

String arTech(String tech) => _techNames[tech] ?? tech;

// ---------------------------------------------------------------------------
// ترجمة الجمل الحرة (أسباب التصنيف، ملاحظات البصمة، تقييم الأولوية...)
// الباك اند يولّدها من قوالب ثابتة، فنترجمها بمطابقة الأنماط مع إبقاء
// الأرقام والقيم كما هي. أي جملة لا تطابق أي نمط تُعرض بنصها الأصلي.
// ---------------------------------------------------------------------------

const _priorityWords = <String, String>{
  'Critical': 'حرجة',
  'High': 'عالية',
  'Medium': 'متوسطة',
  'Low': 'منخفضة',
  'Unknown': 'غير معروفة',
};

const _fixedSentences = <String, String>{
  'Frequency outside catalogued allocations': 'التردد خارج التخصيصات المسجلة',
  'Frequency outside all known allocations, no profile matched':
      'التردد خارج جميع التخصيصات المعروفة، لا يطابق أي نمط',
  'Persistent unidentified transmission': 'إرسال مجهول مستمر',
  'evidence too weak for a definite call': 'الأدلة غير كافية لحكم قاطع',
  'single clean carrier': 'حامل واحد نظيف',
  'Bursty TDMA activity in Iridium band': 'نشاط TDMA متقطع في نطاق إيريديوم',
  'Bursty frame activity (traffic-dependent)': 'نشاط إطارات متقطع (حسب حركة البيانات)',
  'Co-channel interference (overlapping transmission)': 'تداخل بنفس القناة (إرسال متراكب)',
  'Continuous NFM broadcast on NOAA weather allocation': 'بث NFM مستمر على تخصيص طقس NOAA',
  'Continuous downlink (TETRA base station)': 'وصلة هابطة مستمرة (محطة TETRA قاعدية)',
  'Continuous downlink carrier (BCCH always on)': 'حامل وصلة هابطة مستمر (قناة BCCH تعمل دائماً)',
  'Continuous narrow L-band carrier in Inmarsat downlink range':
      'حامل ضيق مستمر في نطاق L ضمن مدى إنمارسات الهابط',
  'Continuous stable downlink (reference signals always on)':
      'وصلة هابطة مستقرة مستمرة (إشارات مرجعية دائمة)',
  'Continuous transmission (always-on broadcast)': 'إرسال مستمر (بث دائم)',
  'Fast fading / possible multipath (power fluctuating)':
      'خفوت سريع / تعدد مسارات محتمل (تذبذب في القدرة)',
  'Frequency hopping observed across the band': 'رُصد قفز ترددي عبر النطاق',
  'GMSK bursts on AIS marine channel': 'دفقات GMSK على قناة AIS البحرية',
  'Multiple short-lived peaks across the band': 'قمم قصيرة العمر متعددة عبر النطاق',
  'Narrow FM push-to-talk channel in PMR/FRS/CB allocation':
      'قناة FM ضيقة (اضغط للتحدث) ضمن تخصيص PMR/FRS/CB',
  'Narrowband interference (steady unmodulated carrier)':
      'تشويش ضيق النطاق (حامل ثابت غير مضمّن)',
  'OFDM multi-carrier (15 kHz subcarriers)': 'OFDM متعدد الحوامل (حوامل فرعية 15 kHz)',
  'One-shot burst then silence (button press)': 'دفقة واحدة ثم صمت (ضغطة زر)',
  'Only thermal noise visible (no significant signal)':
      'ضوضاء حرارية فقط (لا توجد إشارة مهمة)',
  'Overlapping/adjacent transmissions detected': 'رُصدت إرسالات متداخلة/متجاورة',
  'Packet bursts on APRS frequency 144.39 MHz': 'دفقات حزم على تردد APRS ‏144.39 MHz',
  'Periodic slotted activity (TDMA frame structure)': 'نشاط دوري مُقسّم (بنية إطارات TDMA)',
  'Pulsed low-duty activity (Mode S squitters)': 'نشاط نبضي منخفض (إرسالات Mode S)',
  'Push-to-talk activity pattern (transmissions come and go)':
      'نمط اضغط-للتحدث (إرسالات تظهر وتختفي)',
  'RF overload — noise floor jumped, reduce gain or strong nearby transmitter':
      'تحميل راديوي زائد — قفزت أرضية الضوضاء، خفّض الكسب أو يوجد مرسل قوي قريب',
  'Short periodic bursts (advertising interval pattern)':
      'دفقات دورية قصيرة (نمط فترات البث الإعلاني)',
  'Sparse low-duty bursts (mesh sensor traffic)': 'دفقات متفرقة منخفضة (حركة حساسات شبكية)',
  'Strong local 13.56 MHz carrier (near-field reader)':
      'حامل محلي قوي 13.56 MHz (قارئ مجال قريب)',
  'Sustained wideband energy with elevated noise floor':
      'طاقة عريضة النطاق مستمرة مع ارتفاع أرضية الضوضاء',
  'Symmetric spectral peak (clean carrier)': 'قمة طيفية متناظرة (حامل نظيف)',
  'Very low duty cycle (regulatory-limited IoT uplink)':
      'دورة تشغيل منخفضة جداً (وصلة IoT صاعدة محدودة تنظيمياً)',
  'Very strong signal — possible receiver saturation/clipping':
      'إشارة قوية جداً — احتمال تشبع/قص في المستقبل',
  'Wide OFDM block in n78 band': 'كتلة OFDM عريضة في نطاق n78',
  'Wideband noise rise vs recent baseline': 'ارتفاع ضوضاء عريض النطاق مقارنة بالمرجع الأخير',
  '1090 MHz transponder frequency': 'تردد المرسل المستجيب 1090 MHz',
  '12.5 kHz digital channel in public-safety allocation':
      'قناة رقمية 12.5 kHz في تخصيص السلامة العامة',
  'L1 frequency, spread-spectrum signal near/below noise floor':
      'تردد L1، إشارة طيف منثور قرب/تحت أرضية الضوضاء',
  'GLONASS FDMA channel range 1598-1606 MHz': 'مدى قنوات GLONASS FDMA ‏1598-1606 MHz',
  'Galileo E1 shares 1575.42 MHz with GPS L1 (indistinguishable without decoding)':
      'جاليليو E1 يشارك GPS L1 التردد 1575.42 MHz (لا يمكن التمييز بدون فك ترميز)',
  'Narrow bursts in 929-932 MHz FLEX allocation': 'دفقات ضيقة في تخصيص FLEX ‏929-932 MHz',
  'BeiDou B1I frequency 1561.098 MHz': 'تردد بيدو B1I ‏1561.098 MHz',
  '≈2 MHz DSSS channel on the 802.15.4 channel grid':
      'قناة DSSS ‏≈2 MHz على شبكة قنوات 802.15.4',
  'Adjacent-channel activity': 'نشاط في قناة مجاورة',
  'High Occupancy': 'إشغال مرتفع',
  'Interference Suspected': 'اشتباه بتشويش',
  // حقل الاستخدام (use) في قاعدة النطاقات
  'Broadcast Radio': 'إذاعة بث',
  'Short-range RF': 'إرسال RF قصير المدى',
  'Personal Radio': 'راديو شخصي',
  'Consumer Telephony': 'هواتف استهلاكية',
  'Paging': 'أجهزة نداء',
  'Aviation': 'طيران',
  'Satellite Downlink': 'وصلة ساتلية هابطة',
  'Government/Satellite': 'حكومي/أقمار صناعية',
  'Amateur Radio': 'راديو هواة',
  'Paging/Business': 'نداء/أعمال',
  'Maritime': 'بحري',
  'Weather Broadcast': 'بث الطقس',
  'Broadcast TV': 'بث تلفزيوني',
  'Short-range Devices': 'أجهزة قصيرة المدى',
  'Public Safety': 'سلامة عامة',
  'Meteorology': 'أرصاد جوية',
  'Business Radio': 'راديو أعمال',
  'Cellular': 'خلوي',
  'Aviation Surveillance': 'مراقبة طيران',
  'Navigation': 'ملاحة',
  'Satellite Comms': 'اتصالات ساتلية',
  'Short-range/Satellite': 'قصير المدى/ساتلي',
  // أوصاف النطاقات
  'Medium-wave AM broadcasting': 'بث AM على الموجة المتوسطة',
  'Near-field readers and HF RFID': 'قارئات المجال القريب وRFID عالي التردد',
  'Citizens Band channels 1-40': 'قنوات النطاق المدني 1-40',
  'Legacy analog cordless phones': 'هواتف لاسلكية تناظرية قديمة',
  'Legacy VHF paging allocations': 'تخصيصات نداء VHF قديمة',
  'Wideband FM broadcasting': 'بث FM عريض النطاق',
  'Air traffic control and airline data': 'مراقبة الحركة الجوية وبيانات شركات الطيران',
  'Polar weather satellite downlinks': 'وصلات هابطة لأقمار الطقس القطبية',
  'Military and satellite allocations': 'تخصيصات عسكرية وساتلية',
  '2-meter ham band; APRS at 144.39': 'نطاق هواة 2 متر؛ APRS على 144.39',
  'Pagers and business radio': 'أجهزة نداء وراديو أعمال',
  'Ship/coast voice and AIS at 161.975/162.025':
      'اتصالات سفن/سواحل وAIS على 161.975/162.025',
  'Continuous weather radio broadcast': 'بث راديو طقس مستمر',
  'VHF television / digital audio broadcast': 'تلفزيون VHF / بث صوتي رقمي',
  'Low-power remote controls (region-dependent)':
      'أجهزة تحكم منخفضة القدرة (حسب المنطقة)',
  'Emergency-services trunked radio': 'راديو مشترك لخدمات الطوارئ',
  'Weather-balloon telemetry': 'قياسات بالونات الطقس',
  '70-centimeter ham band': 'نطاق هواة 70 سنتيمتر',
  'License-free short-range devices (Region 1)':
      'أجهزة قصيرة المدى بلا ترخيص (المنطقة 1)',
  'License-free walkie-talkies': 'أجهزة لاسلكية يدوية بلا ترخيص',
  'Business/professional two-way radio': 'راديو ثنائي الاتجاه للأعمال',
  'License-free/licensed walkie-talkies (Americas)':
      'أجهزة لاسلكية بلا ترخيص/مرخصة (الأمريكتان)',
  'UHF television broadcasting': 'بث تلفزيوني UHF',
  '700 MHz cellular downlink': 'وصلة خلوية هابطة 700 ميجاهرتز',
  '800 MHz cellular downlink (EU)': 'وصلة خلوية هابطة 800 ميجاهرتز (أوروبا)',
  'Public-safety trunked radio': 'راديو مشترك للسلامة العامة',
  '850 MHz uplink (phones transmit here)': 'وصلة صاعدة 850 ميجاهرتز (الهواتف ترسل هنا)',
  'European license-free IoT band': 'نطاق IoT أوروبي بلا ترخيص',
  '850/900 MHz downlink': 'وصلة هابطة 850/900 ميجاهرتز',
  'Americas license-free IoT band': 'نطاق IoT بلا ترخيص (الأمريكتان)',
  '900 MHz cellular downlink': 'وصلة خلوية هابطة 900 ميجاهرتز',
  'FLEX pager transmitters': 'مرسلات نداء FLEX',
  'Aircraft transponder squitters at 1090 MHz':
      'إرسالات المرسل المستجيب للطائرات على 1090 ميجاهرتز',
  'Modern GNSS civil signals': 'إشارات ملاحة مدنية حديثة',
  'GNSS second frequency': 'التردد الثاني للملاحة الساتلية',
  'Geostationary L-band downlinks': 'وصلات هابطة نطاق L لأقمار ثابتة',
  'Primary GNSS band; all constellations near 1575.42/1602 MHz':
      'نطاق الملاحة الرئيسي؛ جميع المنظومات قرب 1575.42/1602 ميجاهرتز',
  'LEO satellite phone up/downlink': 'وصلات هواتف ساتلية مدارية منخفضة',
  '1800 MHz cellular band': 'نطاق خلوي 1800 ميجاهرتز',
  '1900 MHz cellular band (Americas)': 'نطاق خلوي 1900 ميجاهرتز (الأمريكتان)',
  '2100 MHz downlink': 'وصلة هابطة 2100 ميجاهرتز',
  'The crowded license-free band — shape/behavior analysis decides':
      'النطاق المزدحم بلا ترخيص — تحليل الشكل/السلوك هو الفيصل',
  'Upper edge above Wi-Fi': 'الحافة العليا فوق الواي فاي',
  '2.5-2.7 GHz cellular': 'خلوي 2.5-2.7 جيجاهرتز',
  'Primary mid-band 5G': 'نطاق 5G المتوسط الرئيسي',
  '5 GHz Wi-Fi channels 32-177': 'قنوات واي فاي 5 جيجاهرتز 32-177',
  // قاعدة المعرفة: التصنيفات والفئات
  'Civilian/Broadcast': 'مدني/بث',
  'Civilian/Paging': 'مدني/نداء',
  'Civilian/Personal': 'مدني/شخصي',
  'Civilian': 'مدني',
  'Public Safety/Weather': 'سلامة عامة/طقس',
  'Satellite/Scientific': 'ساتلي/علمي',
  'Satellite/Navigation': 'ساتلي/ملاحة',
  'Satellite/Comms': 'ساتلي/اتصالات',
  'Satellite': 'ساتلي',
  'Short-range/ISM': 'قصير المدى/ISM',
  'Amateur': 'هواة',
  'Industrial/Business': 'صناعي/أعمال',
  // قاعدة المعرفة: النشاط النمطي
  'Continuous': 'مستمر',
  'Intermittent': 'متقطع',
  'Intermittent (push-to-talk)': 'متقطع (اضغط للتحدث)',
  'Continuous bursts': 'دفقات مستمرة',
  'Pass-dependent (10-15 min windows)': 'حسب مرور القمر (نوافذ 10-15 دقيقة)',
  'Very low duty cycle, burst transmission very common':
      'دورة تشغيل منخفضة جداً، إرسال بدفقات شائع',
  'Low duty cycle': 'دورة تشغيل منخفضة',
  'Low-moderate': 'منخفض-متوسط',
  'On-demand (button press)': 'عند الطلب (ضغطة زر)',
  'High occupancy, bursty': 'إشغال مرتفع، متقطع',
  'Bursty, traffic-dependent': 'متقطع حسب حركة البيانات',
  'Continuous (below noise floor)': 'مستمر (تحت أرضية الضوضاء)',
  'Continuous (below noise)': 'مستمر (تحت الضوضاء)',
  'Continuous downlink': 'وصلة هابطة مستمرة',
  'Continuous carriers': 'حوامل مستمرة',
  'Bursty': 'متقطع',
  'Pass/carrier dependent': 'حسب المرور/الحامل',
  // قاعدة المعرفة: الملاحظات التنظيمية
  'Licensed broadcast service in most regions': 'خدمة بث مرخصة في معظم المناطق',
  'Licensed broadcast service': 'خدمة بث مرخصة',
  'Protected aviation allocation worldwide; listening rules vary by country':
      'تخصيص طيران محمي عالمياً؛ قواعد الاستماع تختلف حسب الدولة',
  'Globally harmonized at 1090 MHz': 'موحّد عالمياً على 1090 ميجاهرتز',
  'International maritime mobile allocation': 'تخصيص بحري متنقل دولي',
  'Region-specific (Americas); other regions use different weather services':
      'خاص بالأمريكتين؛ مناطق أخرى تستخدم خدمات طقس مختلفة',
  'Meteorological-satellite service allocation': 'تخصيص خدمة أقمار الأرصاد',
  'License-free short-range band (ITU Region 1); limits vary':
      'نطاق قصير المدى بلا ترخيص (منطقة ITU ‏1)؛ الحدود تختلف',
  'European license-free SRD band with duty-cycle limits':
      'نطاق SRD أوروبي بلا ترخيص مع حدود لدورة التشغيل',
  'Americas license-free ISM band': 'نطاق ISM بلا ترخيص (الأمريكتان)',
  'Region-dependent short-range device band (Americas/Asia)':
      'نطاق أجهزة قصيرة المدى حسب المنطقة (الأمريكتان/آسيا)',
  'Globally license-free; the most crowded band': 'بلا ترخيص عالمياً؛ النطاق الأكثر ازدحاماً',
  'License-free with DFS/radar-protection rules in parts of the band':
      'بلا ترخيص مع قواعد DFS لحماية الرادار في أجزاء من النطاق',
  'Protected radionavigation-satellite allocation; interference here is serious':
      'تخصيص ملاحة راديوية ساتلية محمي؛ التشويش هنا أمر خطير',
  'Public-safety allocation (Europe/MEA); monitoring rules vary by country':
      'تخصيص سلامة عامة (أوروبا/الشرق الأوسط وأفريقيا)؛ قواعد المراقبة تختلف حسب الدولة',
  'Licensed amateur service worldwide': 'خدمة هواة مرخصة عالمياً',
  'Licensed amateur service; shares with ISM 433 in Region 1':
      'خدمة هواة مرخصة؛ تتشارك مع ISM ‏433 في المنطقة 1',
  'Mobile-satellite service allocation': 'تخصيص خدمة ساتلية متنقلة',
  'Licensed cellular spectrum': 'طيف خلوي مرخص',
  'Licensed broadcast spectrum': 'طيف بث مرخص',
  'Licensed paging allocations': 'تخصيصات نداء مرخصة',
  'Protected public-safety spectrum; rules vary by country':
      'طيف سلامة عامة محمي؛ القواعد تختلف حسب الدولة',
  'License-free or lightly licensed personal radio':
      'راديو شخصي بلا ترخيص أو بترخيص مبسط',
  'Protected radionavigation spectrum': 'طيف ملاحة راديوية محمي',
  'Satellite-service allocations': 'تخصيصات خدمات ساتلية',
  'Licensed land-mobile spectrum': 'طيف متنقل بري مرخص',
  'License-free short-range devices; limits vary':
      'أجهزة قصيرة المدى بلا ترخيص؛ الحدود تختلف',
  'Allocation varies by country': 'التخصيص يختلف حسب الدولة',
  'General information — actual allocations and usage vary by country':
      'معلومات عامة — التخصيصات والاستخدام الفعلي يختلفان حسب الدولة',
  // قاعدة المعرفة: التطبيقات والأجهزة الشائعة
  'Music/news broadcasting': 'بث موسيقى/أخبار',
  'News/talk broadcasting': 'بث أخبار/حواري',
  'Air traffic control': 'مراقبة الحركة الجوية',
  'Tower/ground communication': 'اتصالات البرج/الأرض',
  'Airline operations': 'عمليات شركات الطيران',
  'Aircraft surveillance': 'مراقبة الطائرات',
  'Ship-to-ship/shore voice': 'اتصالات سفينة-سفينة/ساحل',
  'Port operations': 'عمليات الموانئ',
  'Distress calling (Ch 16)': 'نداء استغاثة (قناة 16)',
  'Continuous weather broadcast': 'بث طقس مستمر',
  'Hazard alerts': 'تنبيهات مخاطر',
  'Polar weather satellite imagery downlink': 'تنزيل صور أقمار الطقس القطبية',
  'Remote controls': 'أجهزة تحكم عن بُعد',
  'Weather stations': 'محطات طقس',
  'Industrial sensors': 'حساسات صناعية',
  'Alarm systems': 'أنظمة إنذار',
  'Telemetry': 'قياس عن بُعد',
  'Garage door openers': 'فاتحات أبواب الكراج',
  'Key fobs': 'مفاتيح عن بُعد',
  'IoT telemetry': 'قياس IoT عن بُعد',
  'Smart meters': 'عدادات ذكية',
  'LoRaWAN': 'شبكات LoRaWAN',
  'UHF RFID': 'RFID نطاق UHF',
  'Industrial monitoring': 'مراقبة صناعية',
  'Car key fobs': 'مفاتيح سيارات عن بُعد',
  'Garage doors': 'أبواب كراجات',
  'Alarm sensors': 'حساسات إنذار',
  'Wireless networking': 'شبكات لاسلكية',
  'Personal-area networks': 'شبكات شخصية',
  'Smart home': 'منزل ذكي',
  'Peripherals': 'ملحقات',
  'High-throughput Wi-Fi': 'واي فاي عالي السرعة',
  'Satellite navigation': 'ملاحة ساتلية',
  'Ham voice/data': 'صوت/بيانات هواة',
  'APRS position reports': 'تقارير مواقع APRS',
  'Emergency comms practice': 'تدريب اتصالات طوارئ',
  'Repeaters': 'معيدات إرسال',
  'Digital modes': 'أنماط رقمية',
  'Satellite phones': 'هواتف ساتلية',
  'Global IoT': 'إنترنت أشياء عالمي',
  'Maritime/aero satellite comms': 'اتصالات ساتلية بحرية/جوية',
  'Broadcast transmitters': 'مرسلات بث',
  'Car/home receivers': 'مستقبلات سيارة/منزل',
  'MW broadcast transmitters': 'مرسلات بث موجة متوسطة',
  'Aircraft radios': 'أجهزة راديو الطائرات',
  'Control towers': 'أبراج مراقبة',
  'Ground stations': 'محطات أرضية',
  'Aircraft transponders': 'مرسلات مستجيبة للطائرات',
  'Ships': 'سفن',
  'Harbors': 'موانئ',
  'Coast stations': 'محطات ساحلية',
  'Government weather transmitters': 'مرسلات طقس حكومية',
  'NOAA/Meteor satellites': 'أقمار NOAA/ميتيور',
  'Low-power RF devices': 'أجهزة RF منخفضة القدرة',
  'IoT sensors': 'حساسات إنترنت الأشياء',
  'LoRa nodes/gateways': 'عقد/بوابات LoRa',
  'Smart-home sensors': 'حساسات منزل ذكي',
  'RFID readers': 'قارئات RFID',
  'LoRa nodes': 'عقد LoRa',
  'Utility meters': 'عدادات خدمات',
  'Vehicle remotes': 'أجهزة تحكم مركبات',
  'Routers/phones (Wi-Fi)': 'راوترات/هواتف (واي فاي)',
  'Earbuds/wearables (Bluetooth)': 'سماعات/أجهزة قابلة للارتداء (بلوتوث)',
  'Smart-home sensors (Zigbee/Thread)': 'حساسات منزل ذكي (زيجبي/ثريد)',
  'Mice/keyboards': 'فأرات/لوحات مفاتيح',
  'Drones/controllers': 'طائرات مسيّرة/أجهزة تحكم',
  'Routers': 'راوترات',
  'Laptops/phones': 'حواسيب محمولة/هواتف',
  'GPS/Galileo/BeiDou/GLONASS satellites': 'أقمار GPS/جاليليو/بيدو/جلوناس',
  'TETRA base stations': 'محطات TETRA قاعدية',
  'Handhelds': 'أجهزة محمولة يدوياً',
  'Amateur transceivers': 'أجهزة إرسال واستقبال هواة',
  'APRS trackers': 'متتبعات APRS',
  'Iridium LEO satellites': 'أقمار إيريديوم المدارية',
  'Sat phones': 'هواتف ساتلية',
  'Geostationary satellites': 'أقمار ثابتة مدارياً',
  'Terminals': 'محطات طرفية',
  'Unknown': 'غير معروف',
  // أنواع القنوات ورسائل الخادم
  'advertising': 'بث إعلاني',
  'data': 'بيانات',
  'Wi-Fi 2.4GHz': 'واي فاي 2.4 جيجاهرتز',
  'Wi-Fi 5GHz': 'واي فاي 5 جيجاهرتز',
  'Satellite downlink': 'وصلة ساتلية هابطة',
  'Connected to Signal Scope Pi': 'تم الاتصال بجهاز محلل الإشارات',
  // أسماء أحداث RF
  'New Signal Detected': 'تم اكتشاف إشارة جديدة',
  'Possible Frequency Hopper': 'احتمال إشارة قافزة الترددات',
  'Strong Unknown Signal': 'إشارة قوية مجهولة',
  'Possible Wideband Transmission': 'احتمال إرسال عريض النطاق',
  'Long Continuous Transmission': 'إرسال مستمر طويل',
  'Signal Lost': 'اختفت الإشارة',
  'Rapid Activity Increase': 'ازدياد سريع في النشاط',
  'Possible Jammer / RF Overload': 'احتمال تشويش متعمد / تحميل راديوي زائد',
  // أسماء وأنواع الأقمار الصناعية
  'GPS constellation': 'منظومة GPS',
  'Galileo constellation': 'منظومة جاليليو',
  'BeiDou constellation': 'منظومة بيدو',
  'GLONASS constellation': 'منظومة جلوناس',
  'Iridium constellation': 'منظومة إيريديوم',
  'ISS (APRS/voice)': 'محطة الفضاء الدولية (APRS/صوت)',
  'Weather (APT)': 'طقس (APT)',
  'Weather (LRPT)': 'طقس (LRPT)',
  'Navigation (L1 C/A)': 'ملاحة (L1 C/A)',
  'Navigation (E1)': 'ملاحة (E1)',
  'Navigation (L2)': 'ملاحة (L2)',
  'Navigation (L5)': 'ملاحة (L5)',
  'Navigation (B1I)': 'ملاحة (B1I)',
  'Navigation (L1OF)': 'ملاحة (L1OF)',
  'Geostationary comms (L-band)': 'اتصالات ثابتة مدارياً (نطاق L)',
  'LEO comms': 'اتصالات مدار منخفض',
  'LEO broadband (Ku, needs downconverter)': 'إنترنت مدار منخفض (Ku، يحتاج محوّل نزولي)',
  // أسماء أنماط الصوت
  'Periodic Tone': 'نغمة دورية',
  'Beep': 'صافرة قصيرة',
  'Push-To-Talk Voice': 'صوت اضغط-للتحدث',
  'Burst Digital Signal': 'إشارة رقمية بدفقات',
  // جمل تحليل الصوت
  'Data bursts alternating with silence': 'دفقات بيانات تتناوب مع الصمت',
  'Speech segments alternating with silence': 'مقاطع كلام تتناوب مع الصمت',
  'Frame energy below silence threshold': 'طاقة الإطار تحت عتبة الصمت',
  'Morse-like keying': 'نقر يشبه شيفرة مورس',
  'Noise-like but structured spectrum (modem-like)':
      'طيف يشبه الضوضاء لكنه منظّم (يشبه المودم)',
  'Very high zero-crossing rate (broadband)': 'معدل عبور صفري مرتفع جداً (عريض النطاق)',
  'High zero-crossing rate + high centroid (keying-like)':
      'معدل عبور صفري مرتفع + مركز طيفي مرتفع (يشبه النقر)',
  'Weak signal or interference (persistent broadband noise)':
      'إشارة ضعيفة أو تشويش (ضوضاء عريضة مستمرة)',
  'Intermittent reception (signal dropping in and out)':
      'استقبال متقطع (الإشارة تنقطع وتعود)',
  'Zero-crossing rate typical of voiced/unvoiced speech mix':
      'معدل عبور صفري نمطي لمزيج الكلام',
  'Low-pitched harmonic stack (voiced speech F0 range)':
      'توافقيات منخفضة الطبقة (مدى التردد الأساسي للكلام)',
  'Wideband tonal-plus-percussive balance': 'توازن نغمي-إيقاعي عريض النطاق',
  'Whistle (drifting tone)': 'صفير (نغمة منجرفة)',
  'No audio yet': 'لا يوجد صوت بعد',
};

class _Rule {
  final RegExp re;
  final String Function(Match) build;
  const _Rule(this.re, this.build);
}

final _sentenceRules = <_Rule>[
  _Rule(RegExp(r'^Power shifted: (.+) dB -> (.+) dB$'),
      (m) => 'تغيّرت القدرة: من ${m[1]} dB إلى ${m[2]} dB'),
  _Rule(RegExp(r'^Bandwidth shifted: (.+) kHz -> (.+) kHz$'),
      (m) => 'تغيّر عرض النطاق: من ${m[1]} kHz إلى ${m[2]} kHz'),
  _Rule(RegExp(r'^Classification changed: (.+) -> (.+)$'),
      (m) => 'تغيّر التصنيف: من ${arType(m[1]!)} إلى ${arType(m[2]!)}'),
  _Rule(RegExp(r'^Band context: (.+) is typically (\w+)-priority$'),
      (m) => 'سياق النطاق: ${arBand(m[1]!)} عادةً بأولوية ${_priorityWords[m[2]] ?? m[2]}'),
  _Rule(RegExp(r'^Best hypothesis (.+) only (\d+)% — evidence too weak for a definite call$'),
      (m) => 'أفضل فرضية ${arType(m[1]!)} بنسبة ${m[2]}% فقط — الأدلة غير كافية لحكم قاطع'),
  _Rule(RegExp(r'^([\d.]+) MHz in FM broadcast band$'),
      (m) => '${m[1]} MHz ضمن نطاق البث الإذاعي FM'),
  _Rule(RegExp(r'^([\d.]+) MHz in AM broadcast band$'),
      (m) => '${m[1]} MHz ضمن نطاق البث الإذاعي AM'),
  _Rule(RegExp(r'^Matches learned fingerprint \(seen (\d+)×, similarity ([\d.]+)\)$'),
      (m) => 'يطابق بصمة محفوظة (رُصدت ${m[1]}×، التشابه ${m[2]})'),
  _Rule(RegExp(r'^Spectral shape deviates from learned fingerprint \(d=([\d.]+)\)$'),
      (m) => 'شكل الطيف ينحرف عن البصمة المحفوظة (d=${m[1]})'),
  _Rule(RegExp(r'^Feature vector matches learned (.+) prototype \(similarity ([\d.]+), n=(\d+)\)$'),
      (m) => 'الخصائص تطابق نموذج ${arType(m[1]!)} المتعلَّم (التشابه ${m[2]}، العينات ${m[3]})'),
  _Rule(RegExp(r'^Feature vector matches learned (.+) prototype ?(.*)$'),
      (m) => 'الخصائص تطابق نموذج ${arType(m[1]!)} المتعلَّم ${m[2] ?? ''}'.trim()),
  _Rule(RegExp(r'^Statistically unusual vs\. recent history \(anomaly=([\d.]+)\)$'),
      (m) => 'غير اعتيادي إحصائياً مقارنة بالسجل الأخير (شذوذ=${m[1]})'),
  _Rule(RegExp(r'^Anomalous vs\. recent history \((\d+)%\)$'),
      (m) => 'شاذ مقارنة بالسجل الأخير (${m[1]}%)'),
  _Rule(RegExp(r'^Strong unidentified signal \((-?\d+) dB SNR\)$'),
      (m) => 'إشارة قوية غير معروفة (${m[1]} dB نسبة إشارة/ضوضاء)'),
  _Rule(RegExp(r'^Frequency within (.+) allocation \(no shape/behavior match\)$'),
      (m) => 'التردد ضمن تخصيص ${arBand(m[1]!)} (بدون تطابق في الشكل/السلوك)'),
  _Rule(RegExp(r'^~([\d.]+) kSym/s \(est\. from bandwidth\)$'),
      (m) => '~${m[1]} kSym/s (تقديري من عرض النطاق)'),
  _Rule(RegExp(r'^Bandwidth ≈([\d.]+) kHz matches wideband FM$'),
      (m) => 'عرض النطاق ≈${m[1]} kHz يطابق FM عريض النطاق'),
  _Rule(RegExp(r'^Flat-top spectrum \(flatness ([\d.]+)\) matches OFDM$'),
      (m) => 'طيف مسطح القمة (تسطح ${m[1]}) يطابق OFDM'),
  _Rule(RegExp(r'^Flat OFDM spectrum shape \(flatness ([\d.]+)\)$'),
      (m) => 'شكل طيف OFDM مسطح (تسطح ${m[1]})'),
  _Rule(RegExp(r'^Active signals jumped (\d+) → (\d+)$'),
      (m) => 'قفز عدد الإشارات النشطة من ${m[1]} إلى ${m[2]}'),
  _Rule(RegExp(r'^≈([\d.]+) kHz APT downlink shape at 137 MHz$'),
      (m) => 'شكل وصلة APT هابطة ≈${m[1]} kHz عند 137 MHz'),
  _Rule(RegExp(r'^≈([\d.]+) kHz LRPT \(QPSK 72k\) downlink shape$'),
      (m) => 'شكل وصلة LRPT هابطة ≈${m[1]} kHz ‏(QPSK 72k)'),
  _Rule(RegExp(r'^≈([\d.]+) kHz matches LoRa chirp bandwidth \(125/250/500 kHz\)$'),
      (m) => '≈${m[1]} kHz يطابق عرض نطاق LoRa ‏(125/250/500 kHz)'),
  _Rule(RegExp(r'^≈1 MHz channel \(([\d.]+) kHz\) matches BR/EDR hop channel$'),
      (m) => 'قناة ≈1 MHz ‏(${m[1]} kHz) تطابق قناة قفز بلوتوث BR/EDR'),
  _Rule(RegExp(r'^≈2 MHz channel \(([\d.]+) kHz\) on BLE grid$'),
      (m) => 'قناة ≈2 MHz ‏(${m[1]} kHz) على شبكة قنوات BLE'),
  _Rule(RegExp(r'^2 MHz channel centered on BLE advertising frequency \(([\d.]+) MHz\)$'),
      (m) => 'قناة 2 MHz متمركزة على تردد بث BLE الإعلاني (${m[1]} MHz)'),
  _Rule(RegExp(r'^200 kHz channel ≈([\d.]+) kHz on GSM raster$'),
      (m) => 'قناة 200 kHz ‏(≈${m[1]} kHz) على شبكة GSM'),
  _Rule(RegExp(r'^25 kHz TETRA channel ≈([\d.]+) kHz in 380-400 MHz$'),
      (m) => 'قناة TETRA ‏25 kHz ‏(≈${m[1]} kHz) في 380-400 MHz'),
  _Rule(RegExp(r'^12\.5 kHz-class digital channel ≈([\d.]+) kHz$'),
      (m) => 'قناة رقمية من فئة 12.5 kHz ‏(≈${m[1]} kHz)'),
  _Rule(RegExp(r'^Narrow AM channel ≈([\d.]+) kHz in airband$'),
      (m) => 'قناة AM ضيقة ≈${m[1]} kHz في نطاق الطيران'),
  _Rule(RegExp(r'^Narrow OOK/FSK burst ≈([\d.]+) kHz in ISM band$'),
      (m) => 'دفقة OOK/FSK ضيقة ≈${m[1]} kHz في نطاق ISM'),
  _Rule(RegExp(r'^Narrow bandwidth ≈([\d.]+) kHz \(DSB AM\)$'),
      (m) => 'عرض نطاق ضيق ≈${m[1]} kHz ‏(DSB AM)'),
  _Rule(RegExp(r'^Short AFSK bursts \(≈([\d.]+) ms\)$'),
      (m) => 'دفقات AFSK قصيرة (≈${m[1]} ms)'),
  _Rule(RegExp(r'^Short bursts \(≈([\d.]+) ms\) typical of BR/EDR slots$'),
      (m) => 'دفقات قصيرة (≈${m[1]} ms) نمطية لفتحات بلوتوث BR/EDR'),
  _Rule(RegExp(r'^Short data bursts \(≈([\d.]+) ms\) on ACARS-range frequency$'),
      (m) => 'دفقات بيانات قصيرة (≈${m[1]} ms) على تردد ضمن مدى ACARS'),
  _Rule(RegExp(r'^Strong narrow FSK bursts \((-?\d+) dB\) in pager allocation$'),
      (m) => 'دفقات FSK ضيقة قوية (${m[1]} dB) في تخصيص أجهزة النداء'),
  _Rule(RegExp(r'^Very strong continuous carrier \((-?\d+) dB\) in UHF RFID allocation$'),
      (m) => 'حامل مستمر قوي جداً (${m[1]} dB) في تخصيص RFID UHF'),
  _Rule(RegExp(r'^Very wide ≈([\d.]+) MHz OFDM block in NR band$'),
      (m) => 'كتلة OFDM عريضة جداً ≈${m[1]} MHz في نطاق 5G NR'),
  _Rule(RegExp(r'^Wide ≈([\d.]+) MHz block \(OFDM channel\)$'),
      (m) => 'كتلة عريضة ≈${m[1]} MHz ‏(قناة OFDM)'),
  _Rule(RegExp(r'^≈([\d.]+) MHz OFDM block in cellular band$'),
      (m) => 'كتلة OFDM ‏≈${m[1]} MHz في النطاق الخلوي'),
  _Rule(RegExp(r'^≈([\d.]+) MHz occupies most of the view$'),
      (m) => '≈${m[1]} MHz يشغل معظم نافذة العرض'),
  // جمل تحليل الصوت الرقمية
  _Rule(RegExp(r'^19 kHz stereo pilot present \((-?[\d.]+) dB above median\)$'),
      (m) => 'نغمة ستيريو 19 kHz موجودة (${m[1]} dB فوق الوسيط)'),
  _Rule(RegExp(r'^Spectral centroid ([\d.]+) Hz within speech band$'),
      (m) => 'المركز الطيفي ${m[1]} Hz ضمن نطاق الكلام'),
  _Rule(RegExp(r'^High spectral flatness \(([\d.]+)\)$'),
      (m) => 'تسطح طيفي مرتفع (${m[1]})'),
  _Rule(RegExp(r'^Moderate broadband component \(flatness ([\d.]+)\)$'),
      (m) => 'مكوّن عريض النطاق متوسط (تسطح ${m[1]})'),
  _Rule(RegExp(r'^Rich harmonic stack \((\d+) harmonics, (\d+) tonal peaks\)$'),
      (m) => 'توافقيات غنية (${m[1]} توافقية، ${m[2]} قمة نغمية)'),
  _Rule(RegExp(r'^Narrow high-pitched tone at ([\d.]+) Hz \(whistle candidate\)$'),
      (m) => 'نغمة حادة ضيقة عند ${m[1]} Hz (احتمال صفير)'),
  _Rule(RegExp(r'^Sub-audible tone at ([\d.]+) Hz above the local low-band floor$'),
      (m) => 'نغمة تحت مسموعة عند ${m[1]} Hz فوق الأرضية المحلية'),
  _Rule(RegExp(r'^Energy concentrated in a single ([\d.]+) Hz peak\s*(.*)$'),
      (m) => 'الطاقة مركزة في قمة واحدة عند ${m[1]} Hz ${m[2] ?? ''}'.trim()),
  _Rule(RegExp(r'^Tone frequency drifting ±([\d.]+) Hz$'),
      (m) => 'انجراف تردد النغمة ±${m[1]} Hz'),
  _Rule(RegExp(r'^Simultaneous DTMF row\+column pair ([\d.]+)\+([\d.]+) Hz$'),
      (m) => 'زوج DTMF متزامن (صف+عمود) ${m[1]}+${m[2]} Hz'),
  _Rule(RegExp(r'^Standard alert frequency detected \((.+) Hz\)$'),
      (m) => 'رُصد تردد تنبيه قياسي (${m[1]} Hz)'),
  _Rule(RegExp(r'^Short isolated tone burst \(~([\d.]+) s\)$'),
      (m) => 'دفقة نغمة قصيرة معزولة (~${m[1]} ث)'),
  _Rule(RegExp(r'^Short/long tone bursts \(~([\d.]+)/([\d.]+) s\)$'),
      (m) => 'دفقات نغمة قصيرة/طويلة (~${m[1]}/${m[2]} ث)'),
  _Rule(RegExp(r'^every ([\d.]+) s, ~([\d.]+) s each, ×(\d+)$'),
      (m) => 'كل ${m[1]} ث، ~${m[2]} ث لكل واحدة، ×${m[3]}'),
  // تفاصيل أحداث RF
  _Rule(RegExp(r'^(.+) at ([\d.]+) MHz disappeared$'),
      (m) => 'اختفت ${arType(m[1]!)} على ${m[2]} MHz'),
  _Rule(RegExp(r'^(.+) at ([\d.]+) MHz$'),
      (m) => '${arType(m[1]!)} على ${m[2]} MHz'),
  _Rule(RegExp(r'^([\d.]+) dB SNR, unidentified$'),
      (m) => '${m[1]} dB نسبة إشارة/ضوضاء، غير معرَّفة'),
  _Rule(RegExp(r'^(.+) transmitting continuously$'),
      (m) => '${arType(m[1]!)} ترسل باستمرار'),
  _Rule(RegExp(r'^(.+): ([\d.]+)% of the last ([\d.]+) s busy$'),
      (m) => '${arBand(m[1]!)}: ‏${m[2]}% من آخر ${m[3]} ثانية مشغول'),
];

/// يترجم جملة حرة قادمة من الباك اند: مطابقة تامة أولاً، ثم الأنماط،
/// وإلا يُعاد النص الأصلي كما هو (بدون أي كسر للمنطق).
String arSentence(String text) {
  final t = text.trim();
  final exact = _fixedSentences[t];
  if (exact != null) return exact;
  for (final rule in _sentenceRules) {
    final m = rule.re.firstMatch(t);
    if (m != null) return rule.build(m);
  }
  // صيغة "تسمية: جملة" (مثل أسباب تحليل الصوت "Noise: High spectral
  // flatness") — تُترجم التسمية والجملة كل على حدة.
  final sep = t.indexOf(': ');
  if (sep > 0) {
    final head = t.substring(0, sep);
    final tail = t.substring(sep + 2);
    final headAr = _audioLabels[head] ?? _signalTypes[head];
    if (headAr != null) return '$headAr: ${arSentence(tail)}';
  }
  return text;
}
