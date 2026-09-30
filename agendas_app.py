import pdfplumber
import pandas as pd
import warnings
import re
import datetime
import io
import streamlit as st

#fecha de carga para nombrar el archivo de salida:
fecha_carga =  datetime.date.today().strftime("%d/%m/%Y")

#categorias a buscar en titulos dentro del pdf
expected_categories = ["M A R C H A S", "C O N S E N T R A C I O N E S", "R O D A D A S M O T O C I C L I S T A S",
                       "R O D A D A S C I C L I S T A S", "A R T Í S T I C O S", "C U L T U R A L E S", "D E P O R T I V O S",
                       "R E L I G I O S O S","C I T A S A G E N D A D A S"]

#Funcion para identificar la categoria de los eventos y la distancia desde el inicio de la pagina
def identify_category(page):
    #obtenemos las plabras
    words = page.extract_words(extra_attrs=["fontname", "size"])
    top_first = 0
    categorys = 0
    categorias = []
    tops = []
    category_name = ""
    for w in words:
        #Si la palabra tiene las caracteristicas utilizadas en los titulos de categorias
        if (w["fontname"] == "Helvetica-Bold") and (round(w["size"]) >= 18 and round(w["size"]) <= 19):
            #si la palabra es la primera del tipo categoria encontrada
            if top_first == 0:
                top_first = w['top']
                categorys += 1
                category_name = w['text']
            else:
                #Si tiene la misma distancia al tope de pagina se concatena la palabra
                if w['top'] == top_first:
                    category_name += w['text']
                #Si no, se agrega la categoria actual y se inicia una nueva categoria
                else:
                    categorias.append(category_name)
                    tops.append(top_first)
                    categorys += 1
                    category_name = w['text']
                    top_first = w['top']

    #Se agrega la categoria actual
    categorias.append(category_name)
    tops.append(top_first)
    #Se regresan las categorias y las distancias desde el tope donde inician
    return categorias,tops


def identify_events(page, category):
    #obtenemos las plabras
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5)
    lines = {}

    #Las juntamos de acuerdo a su posicion vertical (en lineas)
    for w in words:
        top_rounded = round(w['top'])
        if top_rounded not in lines:
            lines[top_rounded] = []
        lines[top_rounded].append(w)


    lista_lineas = []

    #Unimos las palabras pertenecientes a una misma linea 
    for num_linea in sorted(lines.keys()):            
        line_text = " ".join([w['text'] for w in lines[num_linea]])
        
        linea = {
            "texto": line_text,
            "num_linea": num_linea
        }

        lista_lineas.append(linea)

    unidas = []

    #Concatenamos las lineas que pertenezcan a un mismo parrafo (Segun su separacion vertical)
    for linea in lista_lineas:
        if not unidas:
            unidas.append(linea)
            continue

        previous = unidas[-1]

        if abs(linea["num_linea"] - previous["num_linea"]) <= 10:
            previous["texto"] += " " + linea["texto"]
            previous["num_linea"] = linea["num_linea"]
        else:
            unidas.append(linea)


    filtered_dict = []
    #eliminamos las lineas que contienen la categoria del evento
    for i in range(len(unidas)):
        if unidas[i].get("texto") in expected_categories:
            continue
        else:
            filtered_dict.append(unidas[i])
    
    eventos_final = []
    evento = None
    
    skip_flag = 0
    for i in range(len(filtered_dict)):
        #bandera para saltar las observaciones
        if skip_flag == 0:
            #Si no hay ningun evento previo se inicia el registro del evento
            if evento == None:                
                evento = {
                    "categoria": category,
                    "titulo": filtered_dict[i]["texto"],
                    "texto": ""
                }
                eventos_final.append(evento)
            else:
                #Busca el renglon de fecha
                if "Fecha:" in filtered_dict[i]["texto"]:
                    #Si en cuentra el renglon de fecha y no es el renglon final busca el renglon de aforo
                    if i+1 < len(filtered_dict) and "Aforo:" in filtered_dict[i+1]["texto"]:
                        #Agrega el renglon de fecha al evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        #continua con mas renglones
                        continue
                    #Si no encuentra el renglon de aforo o fecha es el ultimo
                    else:
                        #agrega el renglon de fecha y termina el registro del evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        #Se cambia la bandera para iniciar registro de nuevo evento
                        evento = None
                        continue
                #Busca el renglon de Aforo
                if "Aforo:" in filtered_dict[i]["texto"]:
                    #Si en cuentra el renglon de aforo y no es el renglon final busca el renglon de observaciones
                    if i+1 < len(filtered_dict) and "Observaciones:" in filtered_dict[i+1]["texto"]:
                        #Agrega el renglon de Aforo al evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        #agrega el renglon de Observaciones y termina el registro del evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i+1]["texto"]
                        #Se cambia la bandera para saltar las observaciones
                        skip_flag = 1
                        #Se cambia la bandera para iniciar el registro de un nuevo evento
                        evento = None
                        continue
                    #Si no encuentra el renglon de observaciones o aforo es el ultimo
                    else:
                        #agrega el renglon de aforo y termina el registro del evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        evento = None
                        continue
                #Si no es ninguno de los renglones finales se agrega el renglon al texto del evento              
                else:
                    if eventos_final[-1]["texto"] == "":
                        eventos_final[-1]["texto"] += filtered_dict[i]["texto"]
                    else:
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
        else:
            skip_flag = 0
    #Se devuelve el diccionario de eventos con categoria, titulo y texto
    return eventos_final

#Funcion para obtener los eventos de cada mitad de pagina de acuerdo
#a la categoria a la que pertenece
def obtener_eventos(page, categorias, topes):
    #ordenamos para que las coordenadas no sean negativas
    sorted_floats, sorted_texts = zip(*sorted(zip(topes, categorias), reverse=False))

    #Convertimos las tuplas a listas
    topes = list(sorted_floats)
    categorias = list(sorted_texts)

    eventos_en_pagina = []
    for cat in range(len(categorias)):
            if cat == len(categorias)-1:
                bbox = (0, topes[cat]+20, page.width-90, page.height - 10)
            else:
                bbox = (0, topes[cat]+20, page.width-90, topes[cat+1]-20)

            #Dividimos las paginas de acuerdo a las categorias de eventos
            cropped_page = page.crop(bbox)

            #Dividimos nuevamente por la mitad verticalmente
            bbox1 = (0, 0, cropped_page.width/2, cropped_page.height)
            bbox2 = (cropped_page.width/2, 0, cropped_page.width, cropped_page.height)

            cropped_page1 = cropped_page.crop(bbox1, relative=True)
            cropped_page2 = cropped_page.crop(bbox2, relative=True)

            #usamos la funcion para obtener los eventos en cada mitad de la pagina
            eventos1 = identify_events(cropped_page1, categorias[cat])
            eventos_en_pagina += eventos1
            eventos2 = identify_events(cropped_page2, categorias[cat])
            #Agregamos los eventos de la segunda mitad de la pagina solo si hay
            if len(eventos2) != 0:
                eventos_en_pagina += eventos2

    #Regresamos el diccionario con todos los eventos en la pagina completa
    return eventos_en_pagina

def extract_info(events):
    eventos_finales = []
    for i in events:
        #Buscamos el patron de hora en el texto
        match = re.search(r"Hora:\s*(.*)",i["texto"])
        #Si no se enecuentra le ponemos N/A
        hora = match.group(1) if match else "N/A"
        #Si vienen varias horas se pone solo la primera
        hora = hora.split(',', 1)[0]
        hora = hora.split(' y', 1)[0]
        #Buscamos los posibles lugares a verificar que esten registrados en el shape
        match = re.findall(r"(?:Lugar|Inicia|Termina)(?:\s*\d+)?:\s*(.*)",i["texto"])
        #Si no se encuentra lugar se pone N/A
        lugar =  match if match else "N/A"
        if lugar == "N/A": print("NO SE ENCONTRO NINGUNA UBICACIÓN\n",i)
        #Se busca la fecha del evento
        match = re.search(r"Fecha:\s*(.*)",i["texto"])
        #Si no se encuentra la fecha se le pone N/A
        fecha =  match.group(1) if match else "N/A"


        #LLENADO DE INFORMACIÓN
        #asignacion de categoria y modificacion del titulo correspondiente
        match i["categoria"]:
            case "MARCHAS":
                Categoria, Titulo = "Marchas y movilizaciones", "Marcha "+i["titulo"]
            case "CONCENTRACIONES":
                Categoria, Titulo = "Concentraciones", "Concentración "+i["titulo"]
            case "RODADASMOTOCICLISTAS":
                Categoria, Titulo = "Rodadas Motociclistas", "Rodada Motociclista "+i["titulo"]
            case "RODADASCICLISTAS":
                Categoria, Titulo = "Rodadas Ciclistas", "Rodada Ciclista "+i["titulo"]
            case "RODADASENPATINES":
                Categoria, Titulo = "Rodadas en Patines", "Rodada en Patines "+i["titulo"]
            case "ARTÍSTICOS":
                Categoria, Titulo = "Artísticos", i["titulo"]
            case "CULTURALES":
                Categoria, Titulo = "Culturales", i["titulo"]
            case "DEPORTIVOS":
                Categoria, Titulo = "Deportivos", i["titulo"]
            case "RELIGIOSOS":
                Categoria, Titulo = "Religiosos", i["titulo"]
            case _:  # The underscore acts as the default 'catch-all' case
                print("UKNOWN TYPE OF EVENT FOUND:")
                print(i["categoria"],"\n",i["titulo"])
                Categoria, Titulo = i["categoria"], i["titulo"]


        #A la hora encontrada se le restan 30 minutos y se le suman 3 horas para definir el horario
        if hora != "Durante el día" and hora != "N/A" and hora != "Diversos horarios":
            hor_time = datetime.datetime.strptime(hora, "%H:%M")
            hora_ini = hor_time - datetime.timedelta(minutes=30)
            hora_fin = hora_ini + datetime.timedelta(hours=3)
            horario = "de "+hora_ini.strftime("%H:%M")+" a "+hora_fin.strftime("%H:%M")+" hrs"
            duracion = hora_fin-hora_ini
                        
        #Si no se encuentra horario específico se le asigna un horario de 9 hrs a 15 hrs
        else:
            hora_ini = datetime.datetime.combine(datetime.datetime.today(), datetime.time(9,0))
            #print("DURANTE:",hora_ini)
            hora_fin = hora_ini + datetime.timedelta(hours=6)
            horario = "de "+hora_ini.strftime("%H:%M")+" a "+hora_fin.strftime("%H:%M")+" hrs"
            duracion = datetime.timedelta(hours=6)     

        #Arreglamos la duracion de los eventos para que excel la tome correctamente
        duracion_segundos = int(duracion.total_seconds())
        duracion = datetime.time(hour=(duracion_segundos // 3600), minute=(duracion_segundos % 3600) // 60) 

        print(i)
        print("Categoria:",i["categoria"])
        print("Titulo:",i["titulo"])
        print("HORA:",hora)
        print("Hora inicio:",hora_ini.strftime("%H:%M"))
        print("Hora fin:",hora_fin.strftime("%H:%M"))
        print("Horario:",horario)
        print("Duracion:",duracion)

        if fecha != "N/A":
            print("Fechas:", fecha)
        else:
            fecha = fecha_carga
            print("Fechas:", fecha)
        #sult = new_time.strftime("%H:%M")

        if len(lugar)>1:
            for j in range(len(lugar)):
                print("Lugar",j+1,":",lugar[j])
        else:
            print("Lugar:", lugar[0])

        print("\n")
        evento_extraido = {
                "Llave": "",
                "Carga": "",
                "Fecha": "",
                "Horario": horario,
                "Inicio": hora_ini,
                "Fin": hora_fin,
                "Total": duracion,
                "Evento": Titulo,
                "FOLIO": "",
                "Categoria": Categoria,
                "Categoria_lugar": ""
         }
        eventos_finales.append(evento_extraido)

    print("GENERANDO EXCEL")
    #Creamos un dataframe con la estructura de la agenda de eventos
    df = pd.DataFrame(eventos_finales)
    return df

#######################################MAIN
#titulo de la pagina
st.title("Extracción automática de eventos publicos (PDF a Excel)")

#Seccion para subir el archivo pdf
uploaded_file = st.file_uploader(
    "Selecciona el archivo de agenda (PDF)", type="pdf", accept_multiple_files=False
)

#procesamiento del PDF
if uploaded_file is not None:
  with st.spinner("Procesando PDF..."):
    #Lectura del PDF en memoria
    with pdfplumber.open(uploaded_file) as pdf:
      #Numero de paginas del pdf
      paginas = pdf.pages
      #Diccionario de eventos encontrados en el pdf
      eventos_en_documento = []

      #Se procesa cada pagina del pdf    
      for i in range(1,len(paginas)):
            #Primero obtenemos las categorias que aparecen en cada pagina y 
            #la distancia al tope de la pagina donde comienzan
            categorias,topes = identify_category(paginas[i])
            #Obtenemos los eventos correspondientes a cada categoria en la pagina
            eventos_en_documento += obtener_eventos(paginas[i], categorias, topes)         

    #PARCHE ELIMINAMOS LOS EVENTOS LLAMADOS Itinerario:
    eventos_en_documento = [d for d in eventos_en_documento if d.get("titulo") != "Itinerario:"]

    #Extraemos la informacion que necesitamos de cada evento:
    data_eventos = extract_info(eventos_en_documento)

    #Creamos un flujo de datos en memoria
    output_buffer = io.BytesIO()

    #Generamos el nombre del archivo excel
    filename = f"agenda_{datetime.datetime.today().date()}_automatizada.xlsx"
    #Creamos el archivo de excel
    data_eventos.to_excel(filename, index=False)
    st.success("El archivo de eventos (Excel) fue generado correctamente")

    #Seccion para descargar el archivo de excel generado
    with open(filename, "rb") as file:
        st.download_button(
            label="Descargar archivo de eventos",
            data=file,
            file_name=filename,
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
