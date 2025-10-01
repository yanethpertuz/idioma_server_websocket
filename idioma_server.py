import os
import asyncio
import websockets
import io
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
import logging
from http import HTTPStatus

# Configurar logging para ver mensajes detallados en Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- INICIALIZACIÓN DE HERRAMIENTAS ---
try:
    r = sr.Recognizer()
    translator = Translator()
except Exception as e:
    logging.critical(f"FATAL: No se pudieron inicializar las librerías de traducción: {e}")
    # Si las herramientas principales no se inician, el servidor no puede funcionar.
    # Es mejor que se detenga aquí para que el error sea obvio en los logs.
    raise

CONNECTED_CLIENTS = set()

# --- FUNCIONES DE LÓGICA CON MANEJO DE ERRORES MEJORADO ---
def traducir_audio_stream(audio_bytes):
    lang_codes = (('en-US', 'en'), ('es-ES', 'es'))
    lang1_stt, lang1_tts = lang_codes[0]
    lang2_stt, lang2_tts = lang_codes[1]

    # Paso 1: Crear el objeto AudioData
    try:
        audio_data = sr.AudioData(audio_bytes, sample_rate=44100, sample_width=2)
    except Exception as e:
        logging.error(f"!! Error creando AudioData: {e}")
        return None

    # Paso 2: Transcribir el audio a texto
    texto_detectado = ""
    try:
        texto_detectado = r.recognize_google(audio_data, language=lang1_stt)
    except sr.UnknownValueError:
        try:
            texto_detectado = r.recognize_google(audio_data, language=lang2_stt)
        except sr.UnknownValueError:
            logging.info("-> No se pudo entender el audio.")
            return None
        except Exception as e:
            logging.error(f"!! Error en recognize_google (segundo intento): {e}")
            return None
    except Exception as e:
        logging.error(f"!! Error en recognize_google (primer intento): {e}")
        return None

    if not texto_detectado:
        return None
    logging.info(f"-> Detectado: '{texto_detectado}'")

    # Paso 3: Traducir el texto
    try:
        detected_lang_obj = translator.detect(texto_detectado)
        detected_lang = detected_lang_obj.lang
        destino_tts = lang2_tts if detected_lang == lang1_tts else lang1_tts
        texto_traducido = translator.translate(texto_detectado, dest=destino_tts).text
        logging.info(f"-> Traducido a ({destino_tts}): '{texto_traducido}'")
    except Exception as e:
        logging.error(f"!! Error durante la traducción con googletrans: {e}")
        return None

    # Paso 4: Convertir el texto traducido a audio
    try:
        fp = io.BytesIO()
        gTTS(text=texto_traducido, lang=destino_tts).write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        logging.error(f"!! Error durante la síntesis de voz con gTTS: {e}")
        return None

# --- MANEJO DE WEBSOCKETS (Sin cambios) ---
async def handle_client(websocket, path):
    logging.info(f"[NUEVA CONEXIÓN] Cliente conectado desde {websocket.remote_address}")
    CONNECTED_CLIENTS.add(websocket)
    try:
        async for message in websocket:
            logging.info(f"-> Recibidos {len(message)} bytes de audio.")
            translated_audio = traducir_audio_stream(message)
            if translated_audio:
                logging.info(f"-> Enviando {len(translated_audio)} bytes de audio traducido.")
                tasks = [client.send(translated_audio) for client in CONNECTED_CLIENTS if client != websocket]
                await asyncio.gather(*tasks)
    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"[CONEXIÓN CERRADA] Cliente desconectado: {e.code} {e.reason}")
    except Exception as e:
        logging.error(f"[ERROR INESPERADO] en handle_client: {e}")
    finally:
        if websocket in CONNECTED_CLIENTS:
            CONNECTED_CLIENTS.remove(websocket)
        logging.info(f"Clientes activos: {len(CONNECTED_CLIENTS)}")

async def health_check(path, request_headers):
    if path == "/healthz":
        return HTTPStatus.OK, [], b"OK"

async def main():
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 8765))
    async with websockets.serve(handle_client, HOST, PORT, process_request=health_check):
        logging.info(f"✅ [SERVIDOR WEBSOCKET INICIADO] Escuchando en {HOST}:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"FATAL: El servidor no pudo iniciar: {e}")



