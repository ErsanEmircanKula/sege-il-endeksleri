import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
import numpy as np
import branca.colormap as cm
from streamlit_folium import st_folium

# Sayfa yapılandırması
st.set_page_config(
    layout="wide",
    page_title="SEGE İl Endeksleri Görselleştirme",
    page_icon="🗺️"
)

# CSS stil ekleme
st.markdown(
    """
    <style>
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .stAlert {
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Session state kontrolü
if 'selected_il' not in st.session_state:
    st.session_state.selected_il = None

# Başlık
st.title("🗺️ SEGE İl Endeksleri Analizi")

# Veri yükleme fonksiyonları
@st.cache_data(show_spinner=False)
def load_excel_data():
    try:
        # Excel dosyasını DataFrame olarak oku
        il_data = pd.read_excel("SEGE_ILLER/SEGE Endeksleri.xlsx")
        
        # Veri yapısını kontrol et
        if isinstance(il_data, pd.Series):
            il_data = pd.DataFrame(il_data)
        
        # Yıllara göre sözlük oluştur
        data_dict = {}
        for year in ["2003", "2011", "2017"]:
            data_dict[f'SEGE {year}'] = il_data.copy()
        return data_dict
    except Exception as e:
        st.error(f"❌ Excel verisi yüklenirken hata oluştu: {str(e)}")
        return None

@st.cache_data(show_spinner=False)
def load_geojson_data():
    try:
        gdf = gpd.read_file("HaritaDosyası/Konum_Verileri/TUR_adm1.shp")
        gdf = gdf.rename(columns={'NAME_1': 'name'})
        return gdf
    except Exception as e:
        st.error(f"❌ Harita verisi yüklenemedi: {str(e)}")
        return None

# Verileri yükle
il_data = load_excel_data()
gdf = load_geojson_data()
if il_data is None or gdf is None:
    st.error("❌ Veriler yüklenemedi. Lütfen dosyaların varlığını kontrol edin.")
    st.stop()

# Yıl seçimi
year = st.selectbox("📅 Yıl seçin:", ["2003", "2011", "2017"])

# Seçilen yılın verisini hazırla
@st.cache_data
def prepare_data(year):
    try:
        df = il_data[f'SEGE {year}'].copy()
        
        # DataFrame'e dönüştür
        if isinstance(df, pd.Series):
            df = pd.DataFrame(df)
        
        # Sütun isimlerini kontrol et ve düzelt
        if 'İller' in df.columns:
            df = df.rename(columns={'İller': 'İl'})
        elif 'İl' not in df.columns and len(df.columns) >= 1:
            # İlk sütunu İl olarak varsay
            df = df.rename(columns={df.columns[0]: 'İl'})
        return df
    except Exception as e:
        st.error(f"❌ Veri hazırlama hatası: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def prepare_merged_data(year):
    df = prepare_data(year)
    return gdf.merge(df, left_on='name', right_on='İl', how='left')

df = prepare_data(year)
merged_gdf = prepare_merged_data(year)

# Ana container
main_container = st.container()

with main_container:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📍 {year} Yılı SEGE Haritası")
        
        # İnteraktif harita oluştur
        m = folium.Map(location=[39.9334, 32.8597], zoom_start=6,
                      tiles='CartoDB positron')
        
        # Renk skalası oluştur
        min_val = df['Endeks Değeri'].min()
        max_val = df['Endeks Değeri'].max()
        
        @st.cache_data
        def get_colormap(min_val, max_val, year):
            return cm.LinearColormap(
                colors=['#ff0000', '#ffff00', '#00ff00'],
                vmin=min_val,
                vmax=max_val,
                caption=f'SEGE Endeks Değeri ({year})'
            )
        
        colormap = get_colormap(min_val, max_val, year)

        @st.cache_data
        def create_style_dict(endeks):
            return {
                'fillColor': colormap(endeks),
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.7
            }

        def normalize_str(text):
            """Türkçe karakterleri normalize eder"""
            replacements = {
                'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
                'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S',
                'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            return text

        def style_function(feature):
            il_adi = feature['properties']['name']
            try:
                # İl adını normalize et ve büyük harfe çevir
                normalized_il = normalize_str(il_adi).upper()
                normalized_df_il = df['İl'].apply(lambda x: normalize_str(x).upper())
                il_data = df[normalized_df_il == normalized_il]
                
                if not il_data.empty:
                    endeks = float(il_data['Endeks Değeri'].values[0])
                    return create_style_dict(endeks)
                else:
                    return {
                        'fillColor': 'gray',
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.7
                    }
            except:
                return {
                    'fillColor': 'gray',
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.7
                }

        # GeoJSON katmanı ekle
        gjson = folium.GeoJson(
            data=merged_gdf.__geo_interface__,
            name='SEGE',
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['İl:'],
                style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
            )
        ).add_to(m)

        # Her özellik için popup ekle
        for feature in merged_gdf.iterfeatures():
            il_adi = feature['properties']['name']
            # İl adını normalize et ve büyük harfe çevir
            normalized_il = normalize_str(il_adi).upper()
            normalized_df_il = df['İl'].apply(lambda x: normalize_str(x).upper())
            il_data = df[normalized_df_il == normalized_il]
            
            if not il_data.empty:
                popup_content = f"""<div style="font-family: Arial; font-size: 12px; padding: 10px;">
                    <b>{il_adi}</b><br>
                    Endeks Değeri: {il_data['Endeks Değeri'].values[0]:.4f}<br>
                    Sıra: {il_data['Sıra'].values[0]}<br>
                    Kademe: {il_data['Kademe'].values[0]}
                </div>"""
            else:
                popup_content = f"""<div style="font-family: Arial; font-size: 12px; padding: 10px;">
                    <b>{il_adi}</b><br>
                    Veri bulunamadı
                </div>"""
            
            popup = folium.Popup(popup_content, max_width=300)
            folium.GeoJson(
                feature,
                style_function=lambda x: {'fillOpacity': 0, 'weight': 0},
                popup=popup
            ).add_to(m)
        
        # Renk skalasını haritaya ekle
        colormap.add_to(m)
        
        # Haritayı göster ve tıklama olayını yakala
        map_data = st_folium(m, height=500, width=800)
        
        # Haritadan seçilen ili güncelle
        if map_data['last_clicked']:
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lng = map_data['last_clicked']['lng']
            
            @st.cache_data
            def find_nearest_il(lat, lng, merged_gdf):
                point = gpd.points_from_xy([lng], [lat])
                point_gdf = gpd.GeoDataFrame(geometry=point, crs=merged_gdf.crs)
                distances = merged_gdf.geometry.distance(point_gdf.geometry[0])
                nearest_idx = distances.idxmin()
                il_name = merged_gdf.iloc[nearest_idx]['name']
                
                # İl adını normalize et ve DataFrame'deki il adlarıyla eşleştir
                normalized_il = normalize_str(il_name).upper()
                normalized_df_il = df['İl'].apply(lambda x: normalize_str(x).upper())
                matching_il = df[normalized_df_il == normalized_il]['İl'].values[0]
                
                return matching_il
            
            selected_il = find_nearest_il(clicked_lat, clicked_lng, merged_gdf)
            st.session_state.selected_il = selected_il
    
    with col2:
        st.subheader("📊 İl Bazlı Analiz")
        
        # İl seçimi - haritadan seçilen ili varsayılan olarak göster
        selected_il = st.selectbox("🏙️ İl seçin:", 
                                 df['İl'].tolist(),
                                 index=df['İl'].tolist().index(st.session_state.selected_il) if st.session_state.selected_il in df['İl'].tolist() else 0)
        
        # Session state'i güncelle
        st.session_state.selected_il = selected_il
        
        # Seçilen ilin verilerini göster
        @st.cache_data
        def get_il_data(df, selected_il):
            return df[df['İl'] == selected_il].iloc[0]
        
        il_data_selected = get_il_data(df, selected_il)
        
        # Metrikler
        st.markdown("### 📈 Temel Göstergeler")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🏆 Sıra", il_data_selected['Sıra'])
            st.metric("📊 Kademe", il_data_selected['Kademe'])
        with col2:
            st.metric("📉 Endeks Değeri", round(il_data_selected['Endeks Değeri'], 4))
            st.metric("🌍 Bölge", il_data_selected['Bölge'])

# İstatistiksel analiz bölümü
st.markdown("---")
st.subheader("📊 İstatistiksel Analiz")

# Analiz seçenekleri
analysis_type = st.radio(
    "Analiz türünü seçin:",
    ["Bölgesel Dağılım", "Kademe Analizi", "Korelasyon Analizi"],
    horizontal=True
)

@st.cache_data
def create_analysis_plot(analysis_type, df, year):
    fig = None
    if analysis_type == "Bölgesel Dağılım":
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.boxplot(data=df, x='Bölge', y='Endeks Değeri', ax=ax)
        plt.xticks(rotation=45)
        plt.title(f"{year} Yılı Bölgesel SEGE Dağılımı")
    
    elif analysis_type == "Kademe Analizi":
        kademe_counts = df['Kademe'].value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(10, 6))
        kademe_counts.plot(kind='bar', ax=ax)
        plt.title(f"{year} Yılı Kademe Dağılımı")
        plt.xlabel("Kademe")
        plt.ylabel("İl Sayısı")
    
    elif analysis_type == "Korelasyon Analizi":
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        corr_matrix = df[numeric_cols].corr()
        
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, ax=ax)
        plt.title(f"{year} Yılı Değişkenler Arası Korelasyon")
    
    return fig

fig = create_analysis_plot(analysis_type, df, year)
if fig:
    st.pyplot(fig)

# Footer
st.markdown("---")
st.markdown(
    """
<div style='text-align: center'>
    <p>🌟 SEGE İl Endeksleri Görselleştirme Uygulaması | Geliştirici: Ersan Emircan KULA</p>
</div>
    """,
    unsafe_allow_html=True
)
