import pandas as pd
import streamlit as st
from urllib.parse import unquote, urlparse
from pathlib import PurePosixPath
from st_aggrid import AgGrid, GridUpdateMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import logging
logging.basicConfig(filename='test.log')
CANONICALISED='Canonicalised'
NO_INDEXABLE='Non-Indexable'

def pintaTabla(df_pinta, grid_update, selection):
    gb=GridOptionsBuilder.from_dataframe(df_pinta)
    gb.configure_pagination( paginationAutoPageSize=False,paginationPageSize=20)
    gb.configure_side_bar()  
    if selection:
        gb.configure_selection(selection_mode='multiple',use_checkbox=True)
    gb.configure_default_column(groupable=True, enableRowGroup=True, aggFunc="count")
    grid_options=gb.build()
    if grid_update:
        grid_table=AgGrid(df_pinta,gridOptions=grid_options,update_mode=GridUpdateMode.SELECTION_CHANGED,enable_enterprise_modules=True, editable=True)  
    else:
        grid_table=AgGrid(df_pinta,gridOptions=grid_options,enable_enterprise_modules=True, editable=True)  
    return grid_table

#Obtener los directorios de una URL por nivel
def getPathUrl(url, nivel):
    ruta=''
    paths = urlparse(url).path
    partes=PurePosixPath(unquote(paths)).parts
    if nivel < len(partes):
        i=1
        while i <= nivel:
            ruta+='/'+partes[i]
            i+=1
    return ruta

#Devuelve un DataFrame con los directorioa hasta el nivel definido.
@st.cache_data
def getDirectorios(df_in, nivel_dir,nombre_campo_url):
    i=1
    while i <= nivel_dir:
        df_in['Directorio_'+str(i)]=df_in[nombre_campo_url].apply(lambda x:getPathUrl(x,i))
        i+=1
    return df_in

# Función para obtener la página principal (home) de una URL
@st.cache_data
def obtener_home(url):
    parsed_url = urlparse(url)
    return parsed_url.scheme + "://" + parsed_url.netloc+"/"

#Cuenta el número de keywords que hay en el rango determinado
def cuenta_keywords_en_rango(df_in, pos_ini, pos_fin, campo_posicion):
    df_filtra=df_in[(df_in[campo_posicion]>=pos_ini)&(df_in[campo_posicion]<=pos_fin)]
    cuenta=len(df_filtra.index)
    return cuenta      

#Filtra las URL en formato html o pdf validas en función de si son indexables, parcialmente indexables o todas
@st.cache_data
def filtraURLvalidas(df_in,tipo,formato_url):
    if formato_url=="Sólo HTML":
        content_type='html'
    else:
        content_type='pdf|html'
    if tipo=="Indexables":
        df_mask=(df_in['Content Type'].str.contains(content_type,regex=True))&(df_in["Status Code"]==200)&(df_in['Indexability Status'].isna())
    elif tipo=="Potencialmente indexables":
        df_mask=(df_in['Content Type'].str.contains(content_type,regex=True))&(df_in["Status Code"]==200)&((df_in['Indexability Status'].isna())|(df_in['Indexability Status']).eq(CANONICALISED))
    elif tipo=="Todas 200":
        df_mask=(df_in['Content Type'].str.contains(content_type,regex=True))&(df_in["Status Code"]==200)
    elif tipo=="Todas":
         df_mask=(df_in['Content Type'].str.contains(content_type,regex=True))
    df_out=df_in[df_mask]
    return df_out     

#Filtra URL no indexables
@st.cache_data
def filtraURLNoIndexables(df_in):
    #Los no response realmente no sabemo si son indexables o no
    df_mask=(df_in['Indexability']==NO_INDEXABLE)&(df_in['Indexability Status']!="No Response")
    df_out=df_in[df_mask] 
    return df_out


st.set_page_config(
   page_title="Rendimiento home y directorios"
)
st.title("Rendimiento home y directorios")
st.text("Devuelve datos de keywords posicionadas por directorios")

f_internal=st.file_uploader('CSV con datos exportados de Screaming Frog (internal_all.csv)', type='csv')

if f_internal is not None:
    fuente = st.selectbox(
    'Selecciona la fuente de palabras clave posicionadas',
    ('Ahrefs', 'Sistrix'))
    texto='CSV con datos exportados de '+fuente
    f_keywords=st.file_uploader(texto, type='csv')
    if f_keywords is not None:
        
        if fuente=='Sistrix':
            #Obtenemos el dataframe de los datos de Sistrix
            columnas_keywords=["Palabra clave","Posición","URL"]
            tipo_col_keywords={"Palabra clave": "string", "Posición":int,"URL":"string"}
            #el separador del csv de sistrix es ; y tiene codificación con BOM
            df_keywords=pd.read_csv(f_keywords,sep=";",usecols=columnas_keywords, dtype=tipo_col_keywords,encoding='utf-8-sig')
            #renombramos para homogenizar nombres de columnas en todas las herramientas
            df_keywords=df_keywords.rename(columns={'Palabra clave': 'Keyword', 'Posición':'Position'})
        elif fuente=='Ahrefs':
            #Obtenemos el dataframe de los datos de Ahrefs
            columnas_keywords=["Keyword","Current position","Current URL"]
            #Current position lo ponemos como String porque puede tener valores vacíos
            tipo_col_keywords={"Keyword": "string", "Current position":"string","Current URL":"string"}
            df_keywords=pd.read_csv(f_keywords,usecols=columnas_keywords, dtype=tipo_col_keywords)
            #Eliminamos los valores vacíos de current position
            df_keywords = df_keywords[df_keywords['Current position'] != '']
            df_keywords['Current position'] = df_keywords['Current position'].astype(int)
            #renombramos para homogenizar nombres de columnas en todas las herramientas
            df_keywords=df_keywords.rename(columns={"Current position": 'Position', 'Current URL':'URL'})
        

        #Obtenemos el dataframe de los datos de Screaming
        columnas=["Address","Content Type","Status Code","Indexability","Indexability Status","Crawl Depth",'Unique Inlinks', 'Inlinks','Unique Outlinks', 'Outlinks','Word Count']
        tipo={"Address": "string", "Content Type": "string", "Status Code":int,"Indexability":"string", "Indexability Status":"string","Crawl Depth":int,'Unique Inlinks':int, 'Inlinks':int,'Unique Outlinks':int, 'Outlinks':int,'Word Count':int}
        df_internal=pd.read_csv(f_internal,usecols=columnas, dtype=tipo)
        
        st.header('Posicionamiento de la home')
        #Obtenemos el posicionamiento de la home
        primer_elemento = df_internal.iloc[0]['Address']
        home=obtener_home(primer_elemento)
        #df_home=pd.DataFrame(columns=['URL','Total keywords','Top 3','Top 10',"Top 20",'4-10','11-20','21-50','>50'])
        df_home_tmp=df_keywords[df_keywords['URL']==home]
        total= len(df_home_tmp.index)
        top_3=cuenta_keywords_en_rango(df_home_tmp,1,3,'Position')
        top_10=cuenta_keywords_en_rango(df_home_tmp,1,10,'Position')
        top_20=cuenta_keywords_en_rango(df_home_tmp,1,20,'Position')
        r_4_10=cuenta_keywords_en_rango(df_home_tmp,4,10,'Position')
        r_11_20=cuenta_keywords_en_rango(df_home_tmp,11,20,'Position')
        r_21_50=cuenta_keywords_en_rango(df_home_tmp,21,50,'Position')
        r_51_110=cuenta_keywords_en_rango(df_home_tmp,51,110,'Position')
        dict_home={'URL':[home],'Total keywords':[total],'Top 3':[top_3],'Top 10':[top_10],"Top 20":[top_20],'4-10':[r_4_10],'11-20':[r_11_20],'21-50':[r_21_50],'>50':[r_51_110]}
        df_home=pd.DataFrame(dict_home)
        grid_table_home=pintaTabla(df_home, True, True)
        sel_rows=grid_table_home['selected_rows']
        st.write(type(sel_rows))
        if sel_rows!=None:
            if len(sel_rows) > 0:
                #Filtramos la URL seleccionada para obtener las palabras clave para las que posiciona
                filtro=[]
                for i in sel_rows:
                    n_url=i['URL']
                    filtro.append(n_url)
                boolean_series = df_keywords['URL'].isin(filtro) 
                df_url_seleccionadas=df_keywords[boolean_series]
                grid_table_keywrods=pintaTabla(df_url_seleccionadas,False, False)

        st.header('Posicionamiento por directorios')

        tipo_url= st.radio(
            "Tipo de URL",
            ['Sólo HTML', 'HTML y PDF'], help='Tipos de URL que tendremos en cuenta. Para que cuenta las palabras de los PDF en el crawl debemos habilitar: Spider > Extraction > Store PDF')
        
        tipo_resultados= st.radio(
        "Tipo de URL que tendremos en cuenta",
        ['Indexables', 'Potencialmente indexables', 'Todas 200','Todas'], help='***Indexables***=URL 200, sin noindex y sin canonicalizar\n\n***Potencialmente indexables***=URL 200, sin noindex'+
        '\n\n***Todas 200***=Todas las URL que devuelven 200\n\n***Todas***=Todas las URL rastreadas')
        
        #Filtramos los resultados en función de la opción escogida
        df_filtrado=filtraURLvalidas(df_internal,tipo_resultados,tipo_url)
        
        #Obtenemos la ruta de directorios hasta el nivel especificado
        niveles_directorios=st.number_input(min_value=1,max_value=6,value=2,label='Seleccione el nivel de directorios a obtener')
        #Añadimos una columna para identificar el directorio al que pertenece la URL hasta el nivel de directorio especificado
        df_filtrado=getDirectorios(df_filtrado,niveles_directorios,'Address')
        df_keywords=getDirectorios(df_keywords,niveles_directorios,'URL')
        
        #Columna con el directorio seleccionado
        n_dir='Directorio_'+str(niveles_directorios)
        lista_directorios=df_filtrado[n_dir].unique().tolist()
        #Eliminamos el que venga vacío, porque realmente no existe
        directorios = list(filter(None, lista_directorios))
        #Creamos el dataframe con las columnas iniciales
        df_dir=pd.DataFrame(columns=[n_dir, 'Num Pages', 'Total keywords'])
        #Asignamos el valor a la columna con todos los directorios del nivel establecido
        df_dir[n_dir]=directorios
        #Calculamos el resto de campos
        i=0
        for i in range(len(df_dir)):
            dir_actual=df_dir.loc[i,n_dir]
            #Filtramos del dataframe filtrado todas las URL que pertenecen al directorio actual
            df_temporal=df_filtrado[df_filtrado[n_dir]==dir_actual]
            df_dir.loc[i,"Num Pages"]=len(df_temporal.index)
            #Filtramos todas las URL del fichero con datos de palabra s clave que pertenecen al directorio actual
            df_keywords_temporal=df_keywords[df_keywords[n_dir]==dir_actual]
            #Obtenemos la suma de URL que aparecen posicionando
            df_dir.loc[i,'Total keywords']=len(df_keywords_temporal.index)
            #Obtenemos el rango de posicionamiento
            #df_top=df_keywords_temporal[df_keywords_temporal['Position']<=3]
            df_dir.loc[i,'Top 3']=cuenta_keywords_en_rango(df_keywords_temporal,1,3,'Position')
            df_dir.loc[i,'Top 10']=cuenta_keywords_en_rango(df_keywords_temporal,1,10,'Position')
            df_dir.loc[i,'Top 20']=cuenta_keywords_en_rango(df_keywords_temporal,1,20,'Position')
            df_dir.loc[i,'4-10']=cuenta_keywords_en_rango(df_keywords_temporal,4,10,'Position')
            df_dir.loc[i,'11-20']=cuenta_keywords_en_rango(df_keywords_temporal,11,20,'Position')
            df_dir.loc[i,'21-50']=cuenta_keywords_en_rango(df_keywords_temporal,21,50,'Position')
            df_dir.loc[i,'>50']=cuenta_keywords_en_rango(df_keywords_temporal,51,110,'Position')
        grid_table_resumen=pintaTabla(df_dir, True, True)
        sel_rows=grid_table_resumen['selected_rows']

        if len(sel_rows) > 0:
            #Filtramos los directorios seleccionados para obtener las palabras clave para las que posiciona
            filtro=[]
            for i in sel_rows:
                directorio=i[n_dir]
                filtro.append(directorio)
            boolean_series = df_keywords[n_dir].isin(filtro) 
            df_dir_seleccionados=df_keywords[boolean_series]
            grid_table_keywords=pintaTabla(df_dir_seleccionados,False, False)
        
        st.header('URL no indexables posicionadas')
        df_no_indexable=filtraURLNoIndexables(df_internal)
        lista_URL_no_indexables=df_no_indexable["Address"].to_list()
        df_url_indexadas_no_indexables=df_keywords[df_keywords['URL'].isin(lista_URL_no_indexables)]
        grid_table_indexadas_no_indexables=pintaTabla(df_url_indexadas_no_indexables,True, True)
        sel_rows=grid_table_indexadas_no_indexables['selected_rows']
        if len(sel_rows) > 0:
            #Filtramos las URL seleccionadas para obtener los datos relativos a ellas
            filtro=[]
            for i in sel_rows:
                n_url=i["URL"]
                filtro.append(n_url)
            boolean_series = df_no_indexable["Address"].isin(filtro) 
            df_url_seleccionadas=df_no_indexable[boolean_series]
            grid_table_url_no_indexables=pintaTabla(df_url_seleccionadas,False, False)