import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point
import folium


def compute_growth(df_wide, n_years=3):
    """Считает рост EBIT относительно n_years лет назад."""
    records = []
    year_cols = sorted([c for c in df_wide.columns if c != 'ИНН'])

    for _, row in df_wide.iterrows():
        for year in year_cols:
            base_year = year - n_years
            if base_year not in df_wide.columns:
                continue

            base = row[base_year]
            curr = row[year]

            if pd.isna(base) or pd.isna(curr) or base == 0:
                continue

            growth = (curr - base) / abs(base) * 100
            records.append({
                'ИНН': row['ИНН'],
                'year': int(year),
                'growth': int(round(growth))
            })

    return pd.DataFrame(records, columns=['ИНН', 'year', 'growth'])


def plot_growth_distribution(df_growth, n_years=3, clip_quantiles=(0.01, 0.99),
                             bin_step=10, save_path=None):
    """Строит гистограмму распределения роста EBIT."""
    if df_growth.empty:
        raise ValueError("df_growth пустой — нечего строить")

    lo, hi = df_growth['growth'].quantile(clip_quantiles)
    df_clip = df_growth[(df_growth['growth'] >= lo) & (df_growth['growth'] <= hi)]

    if df_clip.empty:
        df_clip = df_growth

    fig, ax = plt.subplots(figsize=(14, 6))

    if bin_step is None:
        counts = df_clip['growth'].value_counts().sort_index()
        ax.bar(counts.index, counts.values, width=1.0, color='steelblue')
        ax.set_xlabel(f'Рост EBIT относительно {n_years} лет назад, %')
    else:
        bins = np.arange(lo, hi + bin_step, bin_step)
        ax.hist(df_clip['growth'], bins=bins, edgecolor='black', color='steelblue')
        ax.set_xlabel(f'Рост EBIT относительно {n_years} лет назад, % (шаг {bin_step}%)')

    ax.axvline(0, color='red', linestyle='--', alpha=0.7, label='0%')
    ax.set_ylabel('Количество компаний')
    ax.set_title(f'Распределение роста EBIT компаний отрасли 41.20 (N={n_years})')
    ax.grid(axis='y', alpha=0.3)
    ax.legend()
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)

    return fig, ax


def plot_ebit_by_year(df_wide, exclude_outliers=True, threshold=1_000_000, save_path=None):
    """Строит график суммарного EBIT по годам (с опцией исключения выбросов)."""
    years_df = df_wide.drop(columns='ИНН')
    total_all = years_df.sum(skipna=True)
    years = total_all.index.astype(int).astype(str)

    fig, ax = plt.subplots(figsize=(10, 6))

    if exclude_outliers:
        mask = years_df.abs().max(axis=1) < threshold
        total_wo = years_df[mask].sum(skipna=True)

        ax.plot(years, total_all.values, marker='o', label='Все компании')
        ax.plot(years, total_wo.values, marker='s', label=f'Без выбросов (|EBIT| < {threshold:,.0f})')
        ax.legend()
    else:
        ax.bar(years, total_all.values)

    ax.set_xlabel('Год')
    ax.set_ylabel('Суммарный EBIT, тыс. руб.')
    ax.set_title('Суммарный EBIT компаний отрасли 41.20 по годам')
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)

    return fig, ax


def print_growth_stats(df_growth):
    """Выводит в консоль статистику по темпам роста."""
    total = len(df_growth)
    if total == 0:
        print("Нет данных для статистики")
        return

    growing = (df_growth['growth'] > 0).sum()
    falling = (df_growth['growth'] < 0).sum()
    flat = (df_growth['growth'] == 0).sum()

    print(f"Всего наблюдений: {total}")
    print(f"Растущих:       {growing} ({growing/total:.1%})")
    print(f"Падающих:       {falling} ({falling/total:.1%})")
    print(f"Без изменений:  {flat} ({flat/total:.1%})")
    print(f"Медианный рост: {df_growth['growth'].median():.1f}%")
    print(f"IQR (25–75%):   {df_growth['growth'].quantile(0.25):.1f}% … {df_growth['growth'].quantile(0.75):.1f}%")


def plot_companies_map_folium(df, save_html='map_folium.html'):
    """Строит интерактивную карту компаний с помощью Folium."""
    df_map = df.dropna(subset=['lat', 'lon']).copy()
    df_map['avg_ebit'] = df_map['avg_ebit'].fillna(0)
    
    if df_map.empty:
        print("Нет координат для построения карты.")
        return

    m = folium.Map(location=[60.0, 90.0], zoom_start=3, tiles='OpenStreetMap', control_scale=True)

    for _, row in df_map.iterrows():
        ebit_formatted = f"{row['avg_ebit']:,.0f}".replace(",", " ")
        radius = min(20, max(4, row['avg_ebit'] / 30000))
        
        popup_html = f"""
        <div style="font-family: Arial; font-size: 14px;">
            <b>ИНН:</b> {row['ИНН']}<br>
            <b>Средний EBIT:</b> {ebit_formatted} тыс. руб.<br>
            <b>Адрес:</b> {row['address']}
        </div>
        """

        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"ИНН: {row['ИНН']}",
            color='#d9534f',
            fill=True,
            fill_color='#f0ad4e',
            fill_opacity=0.8
        ).add_to(m)

    m.save(save_html)
    print(f"Интерактивная карта сохранена в '{save_html}'")