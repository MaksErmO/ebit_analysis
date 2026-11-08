import pandas as pd
import requests
import time


def data_preparation(excel_path='Реестр.xlsx', csv_path='cleaned_reestr.csv'):
    """Фильтрует исходный реестр ФНС (ЮЛ, МСП, ОКВЭД 41.20) и сохраняет в CSV."""
    try:
        df = pd.read_excel(excel_path, header=2)
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{excel_path}' не найден в папке с проектом.")
        return False

    df = df.dropna(how='all')
    df.columns = df.columns.str.strip()

    df = df[df['Тип субъекта'] == 'Юридическое лицо']
    df = df[df['Категория'].isin(['Малое предприятие', 'Среднее предприятие'])]
    df = df[df['Основной вид деятельности'].str.strip() == '41.20 Строительство жилых и нежилых зданий']
    
    df = df.drop(columns=['№ п/п'], errors='ignore')

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Готово! Отфильтровано {len(df)} компаний. Сохранено в '{csv_path}'.")
    return True


def get_inn():
    """Возвращает список ИНН из очищенного реестра."""
    df = pd.read_csv("cleaned_reestr.csv", dtype={'ИНН': str})
    data_inn = df['ИНН']
    
    # Временно оставил 100 для тестов. Для полного парсинга уберите строку ниже.
    data_inn = data_inn[:100] 
    
    return data_inn


def create_session():
    """Создает HTTP-сессию с заголовками для обхода блокировок."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session


def get_org_id(session, inn):
    """Ищет внутренний ID организации на портале bo.nalog.gov.ru по ИНН."""
    search_url = f"https://bo.nalog.gov.ru/advanced-search/organizations/search?query={inn}&page=0"
    res = session.get(search_url).json()

    if res.get('content') and len(res['content']) > 0:
        return res['content'][0]['id']
    return None


def extract_financials(session, org_id, inn):
    """Собирает EBIT (стр. 2300 + 2330) по годам для заданной организации."""
    bfo_url = f"https://bo.nalog.gov.ru/nbo/organizations/{org_id}/bfo/"
    bfo_data = session.get(bfo_url).json()

    company_data = {'ИНН': inn}

    if not isinstance(bfo_data, list):
        return None

    for report in bfo_data:
        year = report.get('period')
        try:
            fin_res = report['typeCorrections'][0]['correction']['financialResult']
            
            value_2300 = fin_res.get('current2300') or 0
            value_2330 = fin_res.get('current2330') or 0

            company_data[int(year)] = float(value_2300) + float(value_2330)
        except (KeyError, IndexError, TypeError, ValueError):
            continue

    if len(company_data) == 1:
        return None

    return company_data


# Функции ниже использовались один раз для сбора координат.
# В main.py они не вызываются, ключи удалены из кода.

def get_address_by_inn(session, inn, api_key):
    """Возвращает юридический адрес компании по ИНН через DaData."""
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {api_key}"
    }
    payload = {"query": inn, "count": 1}
    
    try:
        response = session.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('suggestions'):
            return data['suggestions'][0]['data'].get('address', {}).get('value')
        return None
    except Exception as e:
        print(f"Ошибка DaData (адрес) для ИНН {inn}: {e}")
        return None


def get_coords_dadata(session, address, api_key, secret_key):
    """Возвращает координаты (lat, lon) по строке адреса через DaData Cleaner."""
    url = "https://cleaner.dadata.ru/api/v1/clean/address"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {api_key}",
        "X-Secret": secret_key
    }
    
    try:
        response = session.post(url, json=[address], headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            lat = result.get('geo_lat')
            lon = result.get('geo_lon')
            if lat and lon:
                return float(lat), float(lon)
        return None, None
    except Exception as e:
        print(f"Ошибка геокодирования для '{address}': {e}")
        return None, None


def enrich_with_coordinates(session, df, api_key, secret_key, address_col='address'):
    """Добавляет колонки 'lat' и 'lon' в DataFrame на основе колонки с адресами."""
    print("\nНачинаем получать координаты...")
    lats = []
    lons = []
    
    for addr in df[address_col]:
        if pd.isna(addr) or addr == "":
            lats.append(None)
            lons.append(None)
            continue
            
        lat, lon = get_coords_dadata(session, addr, api_key, secret_key)
        lats.append(lat)
        lons.append(lon)
        time.sleep(0.1) 
        
    df = df.copy()
    df['lat'] = lats
    df['lon'] = lons
    
    print(f"Успешно геокодировано: {df['lat'].notna().sum()} из {len(df)}")
    return df