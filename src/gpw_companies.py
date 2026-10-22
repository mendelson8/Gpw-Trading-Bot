"""
GPW Companies — company-name to ticker mapping for Warsaw Stock Exchange.

Covers WIG20, mWIG40, and sWIG80 indices (~140 companies).
Includes common aliases, abbreviations, and OCR variants so that
news text can be reliably matched to a GPW ticker.
"""


WIG20_COMPANIES = {
    'ALIOR': 'ALR',
    'ALLEGRO': 'ALE',
    'ASSECO POLAND': 'ACP',
    'ASSECO': 'ACP',
    'CD PROJEKT': 'CDR',
    'CDPROJEKT': 'CDR',
    'DINO': 'DNP',
    'DINO POLSKA': 'DNP',
    'JSW': 'JSW',
    'KGHM': 'KGH',
    'LPP': 'LPP',
    'PEKAO': 'PEO',
    'BANK PEKAO': 'PEO',
    'PGE': 'PGE',
    'PKN ORLEN': 'PKN',
    'PKNORLEN': 'PKN',
    'PKO': 'PKO',
    'PKO BP': 'PKO',
    'PKO BANK POLSKI': 'PKO',
    'PEPCO': 'PCG',
    'PEPCO GROUP': 'PCG',
    'PZU': 'PZU',
    'SANTANDER': 'SPL',
    'SANTANDER BANK POLSKA': 'SPL',
}

MWIG40_COMPANIES = {
    '11 BIT': '11B',
    '11 BIT STUDIOS': '11B',
    'ACAUTOGAZ': 'ACG',
    'ACTION': 'ACT',
    'ASBIS': 'ASB',
    'BENEFIT': 'BFT',
    'BENEFIT SYSTEMS': 'BFT',
    'BNP PARIBAS': 'BNP',
    'BUDIMEX': 'BDX',
    'CCC': 'CCC',
    'CIECH': 'CIE',
    'COGNOR': 'COG',
    'CYFROWY POLSAT': 'CPS',
    'POLSAT': 'CPS',
    'DEVELIA': 'DVL',
    'ECHO': 'ECH',
    'ECHO INVESTMENT': 'ECH',
    'ENEA': 'ENA',
    'EUROCASH': 'EUR',
    'FORTUNA': 'FTE',
    'GRUPA AZOTY': 'ATT',
    'AZOTY': 'ATT',
    'HANDLOWY': 'BHW',
    'BANK HANDLOWY': 'BHW',
    'ING BSK': 'ING',
    'ING BANK': 'ING',
    'INTERCARS': 'CAR',
    'INTER CARS': 'CAR',
    'KRUK': 'KRU',
    'LIVECHAT': 'LVC',
    'LIVECHAT SOFTWARE': 'LVC',
    'MERCATOR': 'MRC',
    'MILLENNIUM': 'MIL',
    'BANK MILLENNIUM': 'MIL',
    'MOL': 'MOL',
    'ORANGE': 'OPL',
    'ORANGE POLSKA': 'OPL',
    'PCC ROKITA': 'PCR',
    'PCCROCKITA': 'PCR',
    'PLAYWAY': 'PLW',
    'POWSZECHNA': 'PZU',
    'TAURON': 'TPE',
    'XTB': 'XTB',
    'WIRTUALNA POLSKA': 'WPL',
    'WP': 'WPL',
}

SWIG80_COMPANIES = {
    'AB': 'ABE',
    'AILLERON': 'ALL',
    'AMICA': 'AMC',
    'ANSWEAR': 'ASW',
    'ANSWEAR.COM': 'ASW',
    'ARTIFEX MUNDI': 'ART',
    'ARTIFEX': 'ART',
    'ASTARTA': 'AST',
    'ATM GRUPA': 'ATG',
    'ATM': 'ATG',
    'BATILONDO': 'BAT',
    'BML': 'BML',
    'BLOOBER': 'BLO',
    'BLOOBER TEAM': 'BLO',
    'BORYSZEW': 'BRS',
    'CALATRAVA': 'CLC',
    'CI GAMES': 'CIG',
    'COMP': 'CMP',
    'COMPERIA': 'CMP',
    'DECORA': 'DCR',
    'ELEKTROTIM': 'ELT',
    'ENEL-MED': 'ENE',
    'ENEL MED': 'ENE',
    'CENTRUM MEDYCZNE ENEL-MED': 'ENE',
    'ESOTIQ': 'ESO',
    'ESOTIQ HENDERSON': 'ESO',
    'ESOTIQ&HENDERSON': 'ESO',
    'FERRUM': 'FER',
    'FOTA': 'FOT',
    'GETIN': 'GTN',
    'GETIN HOLDING': 'GTN',
    'GPW': 'GPW',
    'GIEŁDA PAPIERÓW WARTOŚCIOWYCH': 'GPW',
    'GRUPA KĘTY': 'KTY',
    'KĘTY': 'KTY',
    'Harper Hygienics': 'HPR',
    'HARPER': 'HPR',
    'INC': 'INC',
    'INTERNET MEDIA': 'INP',
    'INP': 'INP',
    'JHM': 'JHM',
    'JHM DEVELOPMENT': 'JHM',
    'KERNEL': 'KER',
    'KOGENERACJA': 'KGN',
    'KOELNER': 'KOL',
    'LUBAWA': 'LBW',
    'MACHINE PROJECT': 'MCP',
    'MENNICY': 'MNC',
    'MONNARI': 'MON',
    'MONNARI TRADE': 'MON',
    'MIRBUD': 'MRB',
    'ML SYSTEM': 'MLS',
    'NEWAG': 'NWG',
    'OŻARÓW': 'OZR',
    'OZARÓW': 'OZR',
    'PEMUG': 'PEM',
    'PEP': 'PEP',
    'POLAND': 'PLD',
    'SIMPLE': 'SMP',
    'SIMPLE SA': 'SMP',
    'STALPRODUKT': 'STP',
    'STX': 'STX',
    'STALEXPORT AUTOSTRADA': 'STX',
    'TEN SQUARE GAMES': 'TSG',
    'TEN SQUARE': 'TSG',
    'TRITON': 'TRI',
    'TRITON DEVELOPMENT': 'TRI',
    'VOXEL': 'VOX',
    'VOXEL SA': 'VOX',
    'WITTCHEN': 'WTN',
    'ZUE': 'ZUE',
}

ALL_TRADEABLE_COMPANIES = {}
ALL_TRADEABLE_COMPANIES.update(WIG20_COMPANIES)
ALL_TRADEABLE_COMPANIES.update(MWIG40_COMPANIES)
ALL_TRADEABLE_COMPANIES.update(SWIG80_COMPANIES)

TRADEABLE_TICKERS = set(ALL_TRADEABLE_COMPANIES.values())

OCR_ALIASES = {
    'MIRBUD': 'MRB',
    'AB': 'ABE',
    'ENEL-MED': 'ENE',
    'ENEL MED': 'ENE',
    'CD PROJEKT': 'CDR',
    'CDPROJEKT': 'CDR',
    'PKN ORLEN': 'PKN',
    'PKNORLEN': 'PKN',
    'PKO BP': 'PKO',
    'PKO BANK POLSKI': 'PKO',
    'DINO POLSKA': 'DNP',
    'BANK PEKAO': 'PEO',
    'CYFROWY POLSAT': 'CPS',
    'BANK MILLENNIUM': 'MIL',
    'ORANGE POLSKA': 'OPL',
    '11 BIT STUDIOS': '11B',
    '11 BIT': '11B',
    'ASSECO POLAND': 'ACP',
    'PEPCO GROUP': 'PCG',
    'SANTANDER BANK POLSKA': 'SPL',
    'BENEFIT SYSTEMS': 'BFT',
    'ECHO INVESTMENT': 'ECH',
    'GRUPA AZOTY': 'ATT',
    'BANK HANDLOWY': 'BHW',
    'ING BANK': 'ING',
    'INTER CARS': 'CAR',
    'LIVECHAT SOFTWARE': 'LVC',
    'PCC ROKITA': 'PCR',
    'WIRTUALNA POLSKA': 'WPL',
    'ANSWEAR.COM': 'ASW',
    'ARTIFEX MUNDI': 'ART',
    'ATM GRUPA': 'ATG',
    'BLOOBER TEAM': 'BLO',
    'ESOTIQ HENDERSON': 'ESO',
    'ESOTIQ&HENDERSON': 'ESO',
    'GETIN HOLDING': 'GTN',
    'GIEŁDA PAPIERÓW WARTOŚCIOWYCH': 'GPW',
    'GRUPA KĘTY': 'KTY',
    'JHM DEVELOPMENT': 'JHM',
    'MONNARI TRADE': 'MON',
    'STALEXPORT AUTOSTRADA': 'STX',
    'TEN SQUARE GAMES': 'TSG',
    'TRITON DEVELOPMENT': 'TRI',
    'VOXEL SA': 'VOX',
    'SIMPLE SA': 'SMP',
    'HARPER HYGIENICS': 'HPR',
    'CENTRUM MEDYCZNE ENEL-MED': 'ENE',
    'mirbud': 'MRB',
    'ab': 'ABE',
    'ccc': 'CCC',
    'xtb': 'XTB',
    'jsw': 'JSW',
    'lpп': 'LPP',
    'kghm': 'KGH',
    'pzu': 'PZU',
    'pkn': 'PKN',
    'pko': 'PKO',
    'pge': 'PGE',
}


def find_ticker_in_text(text):
    """Search for a GPW ticker in a news title or description."""
    if not text:
        return None

    text_upper = text.upper()

    for company_name, ticker in ALL_TRADEABLE_COMPANIES.items():
        if company_name in text_upper:
            return ticker

    return None


def is_ticker_tradeable(ticker):
    """Return True if ticker belongs to WIG20, mWIG40, or sWIG80."""
    if not ticker:
        return False
    return ticker.upper() in TRADEABLE_TICKERS


def get_index_for_ticker(ticker):
    """Return the index name ('WIG20', 'mWIG40', 'sWIG80') for a ticker, or None."""
    if not ticker:
        return None

    ticker = ticker.upper()

    if ticker in WIG20_COMPANIES.values():
        return 'WIG20'
    elif ticker in MWIG40_COMPANIES.values():
        return 'mWIG40'
    elif ticker in SWIG80_COMPANIES.values():
        return 'sWIG80'
    return None


def normalize_ticker(ticker):
    """
    Normalise a ticker or company name to the canonical GPW ticker.

    Examples: 'AB' → 'ABE', 'Mirbud' → 'MRB', 'xtb' → 'XTB'
    """
    if not ticker:
        return None

    ticker_clean = ticker.upper().strip()

    if ticker_clean in OCR_ALIASES:
        return OCR_ALIASES[ticker_clean]

    if ticker_clean in TRADEABLE_TICKERS:
        return ticker_clean

    result = find_ticker_in_text(ticker)
    if result:
        return result

    return ticker_clean


def tickers_match(ticker1, ticker2):
    """Return True if two tickers resolve to the same company (handles aliases)."""
    if not ticker1 or not ticker2:
        return False
    return normalize_ticker(ticker1) == normalize_ticker(ticker2)


def get_company_names_for_ticker(ticker):
    """
    Return all known display names for a ticker (reverse lookup).

    Example: 'ACP' → ['ASSECO', 'ASSECO POLAND']
    """
    if not ticker:
        return []

    ticker_upper = ticker.upper()
    names = []

    all_companies = {}
    all_companies.update(WIG20_COMPANIES)
    all_companies.update(MWIG40_COMPANIES)
    all_companies.update(SWIG80_COMPANIES)

    for name, t in all_companies.items():
        if t == ticker_upper:
            names.append(name.upper())

    if ticker_upper not in names:
        names.append(ticker_upper)

    return list(set(names))
