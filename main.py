import parsing
import plots
import pandas as pd
import matplotlib.pyplot as plt
import os

if __name__ == "__main__":
    if not os.path.exists('cleaned_reestr.csv'):
        parsing.data_preparation()

    # 1. ПАРСИНГ ФИНАНСОВ (EBIT)
    inn_data = parsing.get_inn()
    session = parsing.create_session()
    result = []

    for inn in inn_data:
        org_id = parsing.get_org_id(session, inn)
        company_fin = parsing.extract_financials(session, org_id, inn)
        if company_fin:
            result.append(company_fin)

    df_results = pd.DataFrame(result)
    year_cols = sorted([c for c in df_results.columns if c != 'ИНН'])
    df_results = df_results[['ИНН'] + year_cols]

    # 2. ФИЛЬТРАЦИЯ ТОП-100
    # Считаем средний EBIT по годам, чтобы выбрать крупнейших
    df_results['avg_ebit'] = df_results[year_cols].mean(axis=1)
    df_top100 = df_results.sort_values(by='avg_ebit', ascending=False).head(100).copy()
    print(f"\nОтобрано компаний для карты (Топ-100): {len(df_top100)}")

    # 3. ЗАГРУЗКА ГОТОВЫХ ДАННЫХ ПО АДРЕСАМ
    if not os.path.exists('top100_with_coords.csv'):
        print("\nОШИБКА: Файл 'top100_with_coords.csv' не найден!")
        print("Вам нужно один раз запустить парсинг адресов через DaData, чтобы создать этот файл.")
        df_final = None
    else:
        df_final = pd.read_csv('top100_with_coords.csv')

    # 4. ГРАФИКИ И ВЫВОДЫ (По всей выборке компаний)
    df_clean = df_results.drop(columns=['avg_ebit'])
    
    ebit_by_year = df_clean.drop(columns='ИНН').sum(skipna=True)
    print("\nСуммарный EBIT по годам:")
    print(ebit_by_year)

    plots.plot_ebit_by_year(df_clean, exclude_outliers=True, threshold=1_000_000, save_path='ebit_by_year.png')

    N = 3
    df_growth = plots.compute_growth(df_clean, n_years=N)
    print("\nРост EBIT:")
    print(df_growth.head())

    plots.plot_growth_distribution(df_growth, n_years=N, bin_step=10, save_path='growth_distribution.png')

    plots.print_growth_stats(df_growth)

    # 5. КАРТА
    if df_final is not None:
        plots.plot_companies_map_folium(df_final, save_html='map_folium.html')