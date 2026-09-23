import pdfplumber
import pandas as pd
import warnings
import re
import datetime
import io
import streamlit as st

# 1. Define the path to your PDF
pdf_path = "Agendas/agenda_2026_09_05.pdf"

#fecha de carga:
fecha_carga =  datetime.date.today().strftime("%d/%m/%Y")

events_data = []
expected_categories = ["M A R C H A S", "C O N S E N T R A C I O N E S", "R O D A D A S M O T O C I C L I S T A S",
                       "R O D A D A S C I C L I S T A S", "A R T Í S T I C O S", "C U L T U R A L E S", "D E P O R T I V O S",
                       "R E L I G I O S O S","C I T A S A G E N D A D A S"]

current_event = None
current_category = "GENERAL"

def identify_category(page):
    words = page.extract_words(extra_attrs=["fontname", "size"])
    top_first = 0
    categorys = 0
    categorias = []
    tops = []
    category_name = ""
    for w in words:
        if (w["fontname"] == "Helvetica-Bold") and (round(w["size"]) >= 18 and round(w["size"]) <= 19):
            if top_first == 0:
                top_first = w['top']
                categorys += 1
                category_name = w['text']
            else:
                if w['top'] == top_first:
                    category_name += w['text']
                    #print(category_name)
                else:
                    categorias.append(category_name)
                    tops.append(top_first)
                    categorys += 1
                    category_name = w['text']
                    top_first = w['top']

    categorias.append(category_name)
    tops.append(top_first)

    return categorias,tops


def identify_events(page, category):
    #obtenemos las plabras
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5)
    lines = {}

    #Las juntamos de acuardo a su posicion vertical (en lineas)
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

    #print(lista_lineas)

    unidas = []

    #Concatenamos las lineas que pertenezcan a un mismo parrafo(Segun su separacion vertical)
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
    #eliminamos las lineas que contienen el tipo de evento
    #print("LINEAS UNIDAS:")
    for i in range(len(unidas)):
        #print(unidas[i])
        if unidas[i].get("texto") in expected_categories:
            continue
            #print("Linea eliminada: ",unidas[i])
        else:
            filtered_dict.append(unidas[i])

    
    eventos_final = []
    evento = None
    #print("ya filtrada")
    #print(filtered_dict)

    #print("TAMAÑO:",len(filtered_dict))
    skip_flag = 0
    for i in range(len(filtered_dict)):
        #print(i)
        if skip_flag == 0:
            if evento == None:
                #print("EVENTO AGREGADO")
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
                        evento = None
                        continue
                #Busca el renglon de Aforo
                if "Aforo:" in filtered_dict[i]["texto"]:
                    #Si en cuentra el renglon de aforo y no es el renglon final busca el renglon de observaciones
                    if i+1 < len(filtered_dict) and "Observaciones:" in filtered_dict[i+1]["texto"]:
                        #print("SE encontro observaciones")
                        #print(eventos_final[-1])
                        #Agrega el renglon de Aforo al evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        #print("ADDED:",filtered_dict[i])
                        #agrega el renglon de Observaciones y termina el registro del evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i+1]["texto"]
                        #print("ADDED:",filtered_dict[i+1])
                        skip_flag = 1
                        #print("Saltando observaciones")
                        evento = None
                        continue
                    #Si no encuentra el renglon de observaciones o aforo es el ultimo
                    else:
                        #agrega el renglon de aforo y termina el registro del evento
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
                        evento = None
                        continue
                    
                else:
                    if eventos_final[-1]["texto"] == "":
                        eventos_final[-1]["texto"] += filtered_dict[i]["texto"]
                    else:
                        eventos_final[-1]["texto"] += "\n" + filtered_dict[i]["texto"]
        else:
            skip_flag = 0

    #print("LA FINAL")
    #print(eventos_final)
        
    #for i in range(len(eventos_final)):
    #    print(eventos_final[i]["titulo"])
    #    print(eventos_final[i]["texto"],"\n")
        

    return eventos_final


def obtener_eventos(page, categorias, topes):
    #print("START OBTENER EVENTOS")
    #print("Categorias:",categorias)
    #print("TOPES:",topes)
    #ordenamos para que las coordenadas no sean negativas
    sorted_floats, sorted_texts = zip(*sorted(zip(topes, categorias), reverse=False))

    # 2. Convert tuples back to lists (optional)
    topes = list(sorted_floats)
    categorias = list(sorted_texts)

    #print("ORDENADAS")
    #print("Categorias:",categorias)
    #print("TOPES:",topes)

    
    eventos_en_pagina = []
    for cat in range(len(categorias)):
            if cat == len(categorias)-1:
                #print("ULTIMA CATEGORIA")
                bbox = (0, topes[cat]+20, page.width-90, page.height - 10)
            else:
                bbox = (0, topes[cat]+20, page.width-90, topes[cat+1]-20)

            #Dividimos las paginas de acuerdo al tipo de evento
            #print("CUTTING BOX:",bbox)
            cropped_page = page.crop(bbox)
            #print("EVENTOS DE TIPO ", categorias[cat])
            #print(cropped_page.width, cropped_page.height)
            #cropped_page.to_image().show()

            #Dividimos nuevamente por la mitad
            bbox1 = (0, 0, cropped_page.width/2, cropped_page.height)
            #print(bbox1)
            bbox2 = (cropped_page.width/2, 0, cropped_page.width, cropped_page.height)
            #print(bbox1)

            cropped_page1 = cropped_page.crop(bbox1, relative=True)
            cropped_page2 = cropped_page.crop(bbox2, relative=True)
            #cropped_page1.to_image().show()
            #cropped_page2.to_image().show()

            eventos1 = identify_events(cropped_page1, categorias[cat])
            eventos_en_pagina += eventos1
            #print("LEN:",len(eventos1)," EVENTOS identify 1:",eventos1)
            eventos2 = identify_events(cropped_page2, categorias[cat])
            #print("LEN:",len(eventos2)," EVENTOS identify 2:",eventos2)
            if len(eventos2) != 0:
                eventos_en_pagina += eventos2

            #print("EVENTOS 1:\n")
            #for i in range(len(eventos1)):
            #    print(eventos1[i]["titulo"])
            #    print(eventos1[i]["texto"],"\n")

            #print(eventos1)

            #print("EVENTOS 2:\n")
            #for i in range(len(eventos2)):
            #    print(eventos2[i]["titulo"])
            #    print(eventos2[i]["texto"],"\n")

            #cropped_page1.to_image().show()
            #cropped_page2.to_image().show()
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
st.title("Extracción automática de eventos publicos (PDF a Excel)")

uploaded_file = st.file_uploader(
    "Selecciona el archivo de agenda (PDF)", type="pdf", accept_multiple_files=False
)

if uploaded_file is not None:
  with st.spinner("Procesando PDF..."):
    # Read PDF safely in memory
    with pdfplumber.open(uploaded_file) as pdf:    
      #print("START")
      paginas = pdf.pages
      eventos_en_documento = []
      #print(paginas)
      for i in range(1,len(paginas)):            
            #print("PAGINA: ",paginas[i])
            #Primero obtenemos las categorias que aparecen en cada pagina y 
            #la distancia al tope de la pagina donde comienzan
            categorias,topes = identify_category(paginas[i])
            #Obtenemos los eventos correspondientes a cada categoria en la pagina
            eventos_en_documento += obtener_eventos(paginas[i], categorias, topes)
            #print("COSA FINAL:", eventos_en_pagina)
        
        #print(eventos_en_documento)
    print("COMIENZA CONVERSION A EXCEL")    

    #PARCHE ELIMINAMOS LOS EVENTOS LLAMADOS Itinerario:    
    eventos_en_documento = [d for d in eventos_en_documento if d.get("titulo") != "Itinerario:"]
    #print(eventos_en_documento)
    #         
    #Extraemos la informacion que necesitamos de cada evento:
    data_eventos = extract_info(eventos_en_documento)
    #print(eventos_en_documento)

    # 1. Create an in-memory byte stream instead of a hard-drive file
    output_buffer = io.BytesIO()

    filename = f"agenda_{datetime.datetime.today().date()}_automatizada.xlsx"
    data_eventos.to_excel(filename, index=False)
    st.success("El archivo de eventos (Excel) fue generado correctamente")

    with open(filename, "rb") as file:
        st.download_button(
            label="Descargar archivo de eventos",
            data=file,
            file_name=filename,
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
    
    print("EXCEL GENERADO")
      


    