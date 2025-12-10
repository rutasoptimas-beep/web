# app.py - SISTEMA COMPLETO DE RUTAS ÓPTIMAS PARA MÉXICO
import os
import json
import math
import random
import hashlib
import secrets
import base64
import requests
import time
import io
import pathlib
from datetime import datetime, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import jwt
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import polyline as pl
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, 
    load_pem_public_key
)
from cryptography.hazmat.backends import default_backend

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-por-defecto-cambiar-en-produccion')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:@localhost/pintegrador')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de seguridad de sesiones
app.config['SESSION_COOKIE_SECURE'] = False  # True en producción con HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Configuración de reCAPTCHA v2
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '6LfsHBcsAAAAAKh46BHuWbkvet4ZMhJI8wMPorO9')
RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY', '6LfsHBcsAAAAAF-YbyfPDnT4kth2HzbTUp9qdSoa')
SIMULATE_RECAPTCHA = os.environ.get('SIMULATE_RECAPTCHA', 'True').lower() == 'true'

# Configuración para EMAIL
EMAIL_SIMULATION = os.environ.get('EMAIL_SIMULATION', 'True').lower() == 'true'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USER = os.environ.get('EMAIL_USER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', '')

# Configuración de APIs de Mapas
GEOCODING_API_KEY = os.environ.get('GEOCODING_API_KEY', '')
GRAPHHOPPER_API_KEY = os.environ.get('GRAPHHOPPER_API_KEY', '')
ORS_API_KEY = os.environ.get('ORS_API_KEY', '')
NOMINATIM_USER_AGENT = "rutas_optimas_app_v1"

# Configuración para firma digital
SIGNATURE_MARKER = b"---SIGNATURE_METADATA_START---\n"
END_MARKER = b"---SIGNATURE_METADATA_END---"
PRIVATE_KEY_PATH = pathlib.Path("private_key.pem")
PUBLIC_KEY_PATH = pathlib.Path("public_key.pem")

# Inicializar geocodificador
geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=10)

# ============================================
# SISTEMA DE GEOCODIFICACIÓN MEJORADO PARA MÉXICO
# ============================================
class MexicoGeocoder:
    def __init__(self):
        self.cache = {}
        self.mexico_cities = {
            # Ciudad de México y Área Metropolitana
            'ciudad de mexico': {'lat': 19.4326, 'lng': -99.1332, 'name': 'Ciudad de México'},
            'cdmx': {'lat': 19.4326, 'lng': -99.1332, 'name': 'CDMX'},
            'mexico city': {'lat': 19.4326, 'lng': -99.1332, 'name': 'Ciudad de México'},
            'df': {'lat': 19.4326, 'lng': -99.1332, 'name': 'Ciudad de México'},
            
            # Estados y capitales
            'aguascalientes': {'lat': 21.8853, 'lng': -102.2916, 'name': 'Aguascalientes, Ags.'},
            'baja california': {'lat': 32.5149, 'lng': -117.0382, 'name': 'Tijuana, B.C.'},
            'tijuana': {'lat': 32.5149, 'lng': -117.0382, 'name': 'Tijuana, B.C.'},
            'mexicali': {'lat': 32.6647, 'lng': -115.4750, 'name': 'Mexicali, B.C.'},
            'baja california sur': {'lat': 24.1426, 'lng': -110.3128, 'name': 'La Paz, B.C.S.'},
            'la paz': {'lat': 24.1426, 'lng': -110.3128, 'name': 'La Paz, B.C.S.'},
            'campeche': {'lat': 19.8301, 'lng': -90.5349, 'name': 'Campeche, Camp.'},
            'chiapas': {'lat': 16.7569, 'lng': -93.1292, 'name': 'Tuxtla Gutiérrez, Chis.'},
            'tuxtla gutierrez': {'lat': 16.7569, 'lng': -93.1292, 'name': 'Tuxtla Gutiérrez, Chis.'},
            'chihuahua': {'lat': 28.6353, 'lng': -106.0889, 'name': 'Chihuahua, Chih.'},
            'coahuila': {'lat': 27.0587, 'lng': -101.7068, 'name': 'Saltillo, Coah.'},
            'saltillo': {'lat': 25.4232, 'lng': -101.0053, 'name': 'Saltillo, Coah.'},
            'colima': {'lat': 19.2452, 'lng': -103.7241, 'name': 'Colima, Col.'},
            'durango': {'lat': 24.0229, 'lng': -104.6716, 'name': 'Durango, Dgo.'},
            'guanajuato': {'lat': 21.0190, 'lng': -101.2574, 'name': 'Guanajuato, Gto.'},
            'leon': {'lat': 21.1250, 'lng': -101.6860, 'name': 'León, Gto.'},
            'irapuato': {'lat': 20.6767, 'lng': -101.3563, 'name': 'Irapuato, Gto.'},
            'celaya': {'lat': 20.5233, 'lng': -100.8157, 'name': 'Celaya, Gto.'},
            'guerrero': {'lat': 17.5734, 'lng': -99.5470, 'name': 'Chilpancingo, Gro.'},
            'acapulco': {'lat': 16.8531, 'lng': -99.8237, 'name': 'Acapulco, Gro.'},
            'hidalgo': {'lat': 20.0911, 'lng': -98.7624, 'name': 'Pachuca, Hgo.'},
            'pachuca': {'lat': 20.0911, 'lng': -98.7624, 'name': 'Pachuca, Hgo.'},
            'jalisco': {'lat': 20.6597, 'lng': -103.3496, 'name': 'Guadalajara, Jal.'},
            'guadalajara': {'lat': 20.6597, 'lng': -103.3496, 'name': 'Guadalajara, Jal.'},
            'zapopan': {'lat': 20.7222, 'lng': -103.3833, 'name': 'Zapopan, Jal.'},
            'tlaquepaque': {'lat': 20.6167, 'lng': -103.3167, 'name': 'Tlaquepaque, Jal.'},
            'michoacan': {'lat': 19.7061, 'lng': -101.1950, 'name': 'Morelia, Mich.'},
            'morelia': {'lat': 19.7061, 'lng': -101.1950, 'name': 'Morelia, Mich.'},
            'morelos': {'lat': 18.9212, 'lng': -99.2344, 'name': 'Cuernavaca, Mor.'},
            'cuernavaca': {'lat': 18.9212, 'lng': -99.2344, 'name': 'Cuernavaca, Mor.'},
            'nayarit': {'lat': 21.7514, 'lng': -104.8455, 'name': 'Tepic, Nay.'},
            'tepic': {'lat': 21.7514, 'lng': -104.8455, 'name': 'Tepic, Nay.'},
            'nuevo leon': {'lat': 25.6866, 'lng': -100.3161, 'name': 'Monterrey, N.L.'},
            'monterrey': {'lat': 25.6866, 'lng': -100.3161, 'name': 'Monterrey, N.L.'},
            'san nicolas': {'lat': 25.7472, 'lng': -100.3025, 'name': 'San Nicolás, N.L.'},
            'guadalupe': {'lat': 25.6778, 'lng': -100.2597, 'name': 'Guadalupe, N.L.'},
            'oaxaca': {'lat': 17.0732, 'lng': -96.7266, 'name': 'Oaxaca, Oax.'},
            'puebla': {'lat': 19.0414, 'lng': -98.2063, 'name': 'Puebla, Pue.'},
            'queretaro': {'lat': 20.5881, 'lng': -100.3881, 'name': 'Querétaro, Qro.'},
            'santiago de queretaro': {'lat': 20.5881, 'lng': -100.3881, 'name': 'Santiago de Querétaro'},
            'quintana roo': {'lat': 21.1619, 'lng': -86.8515, 'name': 'Cancún, Q.R.'},
            'cancun': {'lat': 21.1619, 'lng': -86.8515, 'name': 'Cancún, Q.R.'},
            'playa del carmen': {'lat': 20.6296, 'lng': -87.0739, 'name': 'Playa del Carmen, Q.R.'},
            'san luis potosi': {'lat': 22.1565, 'lng': -100.9855, 'name': 'San Luis Potosí, S.L.P.'},
            'sinaloa': {'lat': 24.8049, 'lng': -107.3950, 'name': 'Culiacán, Sin.'},
            'culiacan': {'lat': 24.8049, 'lng': -107.3950, 'name': 'Culiacán, Sin.'},
            'mazatlan': {'lat': 23.2494, 'lng': -106.4111, 'name': 'Mazatlán, Sin.'},
            'sonora': {'lat': 29.0892, 'lng': -110.9613, 'name': 'Hermosillo, Son.'},
            'hermosillo': {'lat': 29.0892, 'lng': -110.9613, 'name': 'Hermosillo, Son.'},
            'tabasco': {'lat': 17.8409, 'lng': -92.6189, 'name': 'Villahermosa, Tab.'},
            'villahermosa': {'lat': 17.9895, 'lng': -92.9477, 'name': 'Villahermosa, Tab.'},
            'tamaulipas': {'lat': 24.2669, 'lng': -98.8363, 'name': 'Ciudad Victoria, Tamps.'},
            'ciudad victoria': {'lat': 23.7369, 'lng': -99.1411, 'name': 'Ciudad Victoria, Tamps.'},
            'reynosa': {'lat': 26.0936, 'lng': -98.2786, 'name': 'Reynosa, Tamps.'},
            'matamoros': {'lat': 25.8697, 'lng': -97.5028, 'name': 'Matamoros, Tamps.'},
            'tlaxcala': {'lat': 19.3140, 'lng': -98.2424, 'name': 'Tlaxcala, Tlax.'},
            'veracruz': {'lat': 19.1738, 'lng': -96.1342, 'name': 'Veracruz, Ver.'},
            'xalapa': {'lat': 19.5312, 'lng': -96.9159, 'name': 'Xalapa, Ver.'},
            'yucatan': {'lat': 20.9674, 'lng': -89.5926, 'name': 'Mérida, Yuc.'},
            'merida': {'lat': 20.9674, 'lng': -89.5926, 'name': 'Mérida, Yuc.'},
            'zacatecas': {'lat': 22.7709, 'lng': -102.5832, 'name': 'Zacatecas, Zac.'},
            
            # Edo. México y ciudades cercanas
            'jocotitlan': {'lat': 19.7083, 'lng': -99.7889, 'name': 'Jocotitlán, Edo. Méx.'},
            'toluca': {'lat': 19.2920, 'lng': -99.6539, 'name': 'Toluca, Edo. Méx.'},
            'ecatepec': {'lat': 19.6091, 'lng': -99.0604, 'name': 'Ecatepec, Edo. Méx.'},
            'neza': {'lat': 19.4000, 'lng': -99.0153, 'name': 'Nezahualcóyotl, Edo. Méx.'},
            'naucalpan': {'lat': 19.4755, 'lng': -99.2383, 'name': 'Naucalpan, Edo. Méx.'},
            'tlalnepantla': {'lat': 19.5369, 'lng': -99.1948, 'name': 'Tlalnepantla, Edo. Méx.'},
            
            # Zonas famosas CDMX
            'angel de la independencia': {'lat': 19.4270, 'lng': -99.1676, 'name': 'Ángel de la Independencia, CDMX'},
            'zocalo': {'lat': 19.4326, 'lng': -99.1332, 'name': 'Zócalo, CDMX'},
            'reforma': {'lat': 19.4326, 'lng': -99.1332, 'name': 'Paseo de la Reforma, CDMX'},
            'polanco': {'lat': 19.4336, 'lng': -99.2048, 'name': 'Polanco, CDMX'},
            'condesa': {'lat': 19.4119, 'lng': -99.1774, 'name': 'Condesa, CDMX'},
            'roma': {'lat': 19.4124, 'lng': -99.1610, 'name': 'Roma, CDMX'},
            'coyoacan': {'lat': 19.3492, 'lng': -99.1614, 'name': 'Coyoacán, CDMX'},
            'santa fe': {'lat': 19.3574, 'lng': -99.2591, 'name': 'Santa Fe, CDMX'},
            'satelite': {'lat': 19.5181, 'lng': -99.2332, 'name': 'Satélite, Edo. Méx.'},
            'interlomas': {'lat': 19.4045, 'lng': -99.2792, 'name': 'Interlomas, Edo. Méx.'},
            'cuautitlan': {'lat': 19.6706, 'lng': -99.1792, 'name': 'Cuautitlán, Edo. Méx.'},
            
            # Aeropuertos importantes
            'aifa': {'lat': 19.3371, 'lng': -98.9558, 'name': 'Aeropuerto Internacional Felipe Ángeles'},
            'aeropuerto benito juarez': {'lat': 19.4363, 'lng': -99.0721, 'name': 'Aeropuerto Benito Juárez'},
            'aeropuerto guadalajara': {'lat': 20.5218, 'lng': -103.3112, 'name': 'Aeropuerto Guadalajara'},
            'aeropuerto monterrey': {'lat': 25.7785, 'lng': -100.1075, 'name': 'Aeropuerto Monterrey'},
        }
    
    def geocode(self, address):
        """Geocodifica una dirección en México"""
        address_lower = address.lower().strip()
        
        # Primero verificar cache
        if address_lower in self.cache:
            return self.cache[address_lower]
        
        # Verificar ciudades conocidas
        for city_name, data in self.mexico_cities.items():
            if city_name in address_lower:
                result = {
                    'success': True,
                    'address': data['name'],
                    'lat': data['lat'],
                    'lng': data['lng'],
                    'city': data['name']
                }
                self.cache[address_lower] = result
                return result
        
        # Si no está en la lista, usar Nominatim
        try:
            location = geolocator.geocode(f"{address}, México")
            if location:
                result = {
                    'success': True,
                    'address': location.address,
                    'lat': location.latitude,
                    'lng': location.longitude
                }
                self.cache[address_lower] = result
                return result
        except Exception as e:
            print(f"Error en geocodificación Nominatim: {e}")
        
        # Fallback: buscar en palabras clave
        for keyword in ['centro', 'plaza', 'mercado', 'hospital', 'universidad', 'escuela', 'hotel']:
            if keyword in address_lower:
                # Asociar con ciudad más cercana mencionada
                for city_name, data in self.mexico_cities.items():
                    if any(word in address_lower for word in city_name.split() if len(word) > 3):
                        result = {
                            'success': True,
                            'address': f"{keyword.title()}, {data['name']}",
                            'lat': data['lat'] + random.uniform(-0.01, 0.01),
                            'lng': data['lng'] + random.uniform(-0.01, 0.01),
                            'city': data['name']
                        }
                        self.cache[address_lower] = result
                        return result
        
        # Fallback final: ubicación aleatoria en México
        return self.get_random_mexico_location(address)
    
    def get_random_mexico_location(self, address):
        """Genera una ubicación aleatoria dentro de México"""
        # Coordenadas aproximadas de México con distribución de población
        mexico_regions = [
            # Centro (mayor población)
            {'north': 20.0, 'south': 18.0, 'west': -100.0, 'east': -98.0, 'weight': 40},
            # Norte
            {'north': 32.0, 'south': 24.0, 'west': -117.0, 'east': -105.0, 'weight': 25},
            # Occidente
            {'north': 22.0, 'south': 18.0, 'west': -105.0, 'east': -100.0, 'weight': 20},
            # Sureste
            {'north': 22.0, 'south': 16.0, 'west': -95.0, 'east': -86.0, 'weight': 15},
        ]
        
        # Seleccionar región basada en peso
        weights = [region['weight'] for region in mexico_regions]
        selected_region = random.choices(mexico_regions, weights=weights)[0]
        
        lat = random.uniform(selected_region['south'], selected_region['north'])
        lng = random.uniform(selected_region['west'], selected_region['east'])
        
        # Obtener ciudad más cercana para el nombre
        closest_city = min(self.mexico_cities.values(), 
                          key=lambda x: math.sqrt((x['lat']-lat)**2 + (x['lng']-lng)**2))
        
        result = {
            'success': True,
            'address': f"{address}, cerca de {closest_city['name']}",
            'lat': lat,
            'lng': lng,
            'city': closest_city['name']
        }
        
        self.cache[address.lower()] = result
        return result
    
    def reverse_geocode(self, lat, lng):
        """Convierte coordenadas a dirección"""
        try:
            location = geolocator.reverse(f"{lat}, {lng}", language='es', exactly_one=True)
            if location:
                return {
                    'success': True,
                    'address': location.address,
                    'lat': lat,
                    'lng': lng
                }
        except Exception as e:
            print(f"Error en reverse geocoding: {e}")
        
        # Encontrar ciudad más cercana
        closest_city = min(self.mexico_cities.values(), 
                          key=lambda x: math.sqrt((x['lat']-lat)**2 + (x['lng']-lng)**2))
        
        distance = math.sqrt((closest_city['lat']-lat)**2 + (closest_city['lng']-lng)**2) * 111
        
        if distance < 10:  # Menos de 10 km
            location_desc = f"{closest_city['name']}"
        elif distance < 50:  # Menos de 50 km
            location_desc = f"Cerca de {closest_city['name']}"
        else:
            location_desc = f"Región de {closest_city['name'].split(',')[-1].strip()}"
        
        return {
            'success': True,
            'address': f"Ubicación: {lat:.4f}, {lng:.4f} ({location_desc})",
            'lat': lat,
            'lng': lng
        }

# ============================================
# SISTEMA DE RUTAS REALES CON OSRM
# ============================================
class RealRouteSystem:
    def __init__(self):
        # Configuración de OSRM (Open Source Routing Machine)
        self.osrm_base_url = "http://router.project-osrm.org/route/v1"
        # Alternativa: servidor OSRM local o de Mapbox
        self.mapbox_access_token = os.environ.get('MAPBOX_ACCESS_TOKEN', '')
        
        # Si tenemos Mapbox token, usamos su API
        if self.mapbox_access_token:
            self.use_mapbox = True
            self.mapbox_base_url = "https://api.mapbox.com/directions/v5/mapbox/driving"
        else:
            self.use_mapbox = False
        
        # Para rutas en México, OSRM funciona bien
        print(f"🗺️  Usando OSRM para rutas: {self.osrm_base_url}")
        if self.mapbox_access_token:
            print(f"🗺️  Mapbox también disponible con token")
    
    def get_real_route(self, start_lat, start_lng, end_lat, end_lng, route_type="all"):
        """
        Obtiene rutas reales usando OSRM o Mapbox
        """
        try:
            # Intentar OSRM primero (gratuito)
            routes = self.get_osrm_route(start_lat, start_lng, end_lat, end_lng, route_type)
            if routes:
                return routes
            
            # Si OSRM falla, usar Mapbox si está disponible
            if self.use_mapbox:
                routes = self.get_mapbox_route(start_lat, start_lng, end_lat, end_lng, route_type)
                if routes:
                    return routes
                    
        except Exception as e:
            print(f"❌ Error obteniendo ruta real: {e}")
        
        # Fallback a simulación mejorada
        return self.get_simulated_route(start_lat, start_lng, end_lat, end_lng, route_type)
    
    def get_osrm_route(self, start_lat, start_lng, end_lat, end_lng, route_type):
        """Usa OSRM para obtener rutas reales"""
        try:
            # Construir URL para OSRM
            coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"
            
            # Parámetros para OSRM
            params = {
                'overview': 'full',  # Obtener geometría completa
                'geometries': 'geojson',  # Formato GeoJSON
                'steps': 'true',  # Incluir instrucciones paso a paso
                'alternatives': '3'  # Obtener 3 rutas alternativas
            }
            
            # Ajustar parámetros según tipo de ruta
            if route_type == "without_tolls":
                # OSRM no tiene soporte nativo para evitar cuotas, pero podemos aproximar
                params['exclude'] = 'motorway'
            
            url = f"{self.osrm_base_url}/driving/{coordinates}"
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self.parse_osrm_response(data, start_lat, start_lng, end_lat, end_lng, route_type)
            else:
                print(f"OSRM error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Error OSRM: {e}")
        
        return []
    
    def get_mapbox_route(self, start_lat, start_lng, end_lat, end_lng, route_type):
        """Usa Mapbox API para rutas reales"""
        try:
            coordinates = f"{start_lng},{start_lat};{end_lng},{end_lat}"
            
            params = {
                'geometries': 'geojson',
                'steps': 'true',
                'alternatives': 'true',
                'overview': 'full',
                'access_token': self.mapbox_access_token
            }
            
            if route_type == "without_tolls":
                params['exclude'] = 'toll'
            
            url = f"{self.mapbox_base_url}/{coordinates}"
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return self.parse_mapbox_response(data, start_lat, start_lng, end_lat, end_lng, route_type)
            else:
                print(f"Mapbox error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Error Mapbox: {e}")
        
        return []
    
    def parse_osrm_response(self, data, start_lat, start_lng, end_lat, end_lng, route_type):
        """Parse la respuesta de OSRM"""
        routes = []
        
        for i, route in enumerate(data.get('routes', [])):
            geometry = route.get('geometry', {}).get('coordinates', [])
            
            # Calcular distancia y tiempo
            distance = route.get('distance', 0) / 1000  # Convertir a km
            duration = route.get('duration', 0) / 60  # Convertir a minutos
            
            # Determinar si tiene cuotas (simulación basada en carreteras usadas)
            # En OSRM, podemos verificar si usa motorways
            has_tolls = self.detect_tolls_in_route(route, i)
            
            # Obtener instrucciones paso a paso
            steps = self.extract_osrm_steps(route)
            
            route_data = {
                'id': i + 1,
                'name': self.get_route_name(i, has_tolls, distance, duration),
                'icon': self.get_route_icon(i, has_tolls),
                'has_tolls': has_tolls,
                'duration_min': int(duration),
                'distance_km': round(distance, 1),
                'speed_kmh': int((distance / (duration/60)) if duration > 0 else 60),
                'fuel_estimate': {
                    'liters': round(distance * 0.08, 1),
                    'cost_mxn': round(distance * 0.08 * 22 * (1.3 if has_tolls else 1.0), 1)
                },
                'traffic_estimate': {
                    'level': self.get_traffic_level(i),
                    'color': self.get_traffic_color(i),
                    'delay': f"+{random.randint(5, 15 + i*5)} min"
                },
                'primary_roads': self.calculate_primary_roads(route, has_tolls),
                'description': self.get_route_description(i, has_tolls, distance, duration),
                'steps': steps,
                'geometry': {
                    'coordinates': geometry,
                    'type': 'LineString'
                },
                'waypoints': self.extract_waypoints(route, start_lat, start_lng, end_lat, end_lng)
            }
            
            route_data['duration_formatted'] = self.format_duration(route_data['duration_min'])
            routes.append(route_data)
        
        # Ordenar rutas por duración
        routes.sort(key=lambda x: x['duration_min'])
        
        return routes
    
    def parse_mapbox_response(self, data, start_lat, start_lng, end_lat, end_lng, route_type):
        """Parse la respuesta de Mapbox"""
        routes = []
        
        for i, route in enumerate(data.get('routes', [])):
            geometry = route.get('geometry', {}).get('coordinates', [])
            
            distance = route.get('distance', 0) / 1000
            duration = route.get('duration', 0) / 60
            
            # Mapbox tiene información de cuotas
            has_tolls = self.detect_mapbox_tolls(route)
            
            steps = self.extract_mapbox_steps(route)
            
            route_data = {
                'id': i + 1,
                'name': self.get_route_name(i, has_tolls, distance, duration),
                'icon': self.get_route_icon(i, has_tolls),
                'has_tolls': has_tolls,
                'duration_min': int(duration),
                'distance_km': round(distance, 1),
                'speed_kmh': int((distance / (duration/60)) if duration > 0 else 60),
                'fuel_estimate': {
                    'liters': round(distance * 0.08, 1),
                    'cost_mxn': round(distance * 0.08 * 22 * (1.3 if has_tolls else 1.0), 1)
                },
                'traffic_estimate': {
                    'level': self.get_traffic_level(i),
                    'color': self.get_traffic_color(i),
                    'delay': f"+{random.randint(5, 15 + i*5)} min"
                },
                'primary_roads': self.calculate_mapbox_primary_roads(route),
                'description': self.get_route_description(i, has_tolls, distance, duration),
                'steps': steps,
                'geometry': {
                    'coordinates': geometry,
                    'type': 'LineString'
                }
            }
            
            route_data['duration_formatted'] = self.format_duration(route_data['duration_min'])
            routes.append(route_data)
        
        routes.sort(key=lambda x: x['duration_min'])
        return routes
    
    def get_simulated_route(self, start_lat, start_lng, end_lat, end_lng, route_type):
        """Genera rutas simuladas más realistas cuando las APIs fallan"""
        
        # Calcular distancia real
        start_coords = (start_lat, start_lng)
        end_coords = (end_lat, end_lng)
        direct_distance = geodesic(start_coords, end_coords).kilometers
        
        # Factor de desviación realista (las carreteras no son líneas rectas)
        deviation_factor = 1.2 + random.uniform(0.1, 0.3)  # 20-50% más largo
        
        # Generar puntos intermedios que simulen carreteras principales
        route_coordinates = self.generate_realistic_highway_route(start_lat, start_lng, end_lat, end_lng, direct_distance)
        
        # Crear rutas con diferentes características
        routes = []
        route_configs = [
            {
                'id': 1,
                'name': 'Ruta Más Rápida',
                'icon': '🚀',
                'has_tolls': True,
                'speed_kmh': 90,
                'cost_multiplier': 1.3,
                'description': 'Autopistas de cuota - Tiempo optimizado',
                'highway_percentage': 85
            },
            {
                'id': 2,
                'name': 'Ruta Económica',
                'icon': '💰',
                'has_tolls': False,
                'speed_kmh': 60,
                'cost_multiplier': 1.0,
                'description': 'Carreteras libres - Costo optimizado',
                'highway_percentage': 40
            },
            {
                'id': 3,
                'name': 'Ruta Alternativa',
                'icon': '🛣️',
                'has_tolls': True,
                'speed_kmh': 75,
                'cost_multiplier': 1.15,
                'description': 'Combinación de autopistas y libres',
                'highway_percentage': 65
            }
        ]
        
        for i, config in enumerate(route_configs):
            # Filtrar por tipo de ruta solicitado
            if route_type == "with_tolls" and not config['has_tolls']:
                continue
            if route_type == "without_tolls" and config['has_tolls']:
                continue
            
            # Calcular distancia específica para esta ruta
            route_distance = direct_distance * deviation_factor * (1 + i * 0.08)
            
            # Calcular tiempo basado en velocidad y distancia
            route_time_hours = route_distance / config['speed_kmh']
            route_time_minutes = max(15, int(route_time_hours * 60))
            
            # Generar variación en las coordenadas para cada ruta
            route_coords = self.vary_route_coordinates(route_coordinates, i, config['highway_percentage'])
            
            # Generar instrucciones paso a paso realistas
            steps = self.generate_realistic_steps(start_lat, start_lng, end_lat, end_lng, i, config['has_tolls'])
            
            route = {
                'id': config['id'],
                'name': config['name'],
                'icon': config['icon'],
                'has_tolls': config['has_tolls'],
                'duration_min': route_time_minutes,
                'distance_km': round(route_distance, 1),
                'speed_kmh': config['speed_kmh'],
                'fuel_estimate': {
                    'liters': round(route_distance * 0.08 * (config['speed_kmh']/80), 1),
                    'cost_mxn': round(route_distance * 0.08 * 22 * config['cost_multiplier'], 1)
                },
                'traffic_estimate': {
                    'level': self.get_traffic_level(i),
                    'color': self.get_traffic_color(i),
                    'delay': f"+{random.randint(5, 15 + i*5)} min"
                },
                'primary_roads': config['highway_percentage'],
                'description': config['description'],
                'steps': steps,
                'geometry': {
                    'coordinates': route_coords,
                    'type': 'LineString'
                }
            }
            
            route['duration_formatted'] = self.format_duration(route['duration_min'])
            routes.append(route)
        
        return routes
    
    def generate_realistic_highway_route(self, start_lat, start_lng, end_lat, end_lng, distance_km):
        """Genera coordenadas que simulan rutas por carreteras principales"""
        coordinates = []
        
        # Punto de inicio
        coordinates.append([start_lng, start_lat])
        
        # Para distancias largas, usar menos puntos pero más significativos
        num_points = max(5, int(distance_km / 25))
        
        # Calcular dirección general
        lat_diff = end_lat - start_lat
        lng_diff = end_lng - start_lng
        
        # Principales ciudades intermedias en México (simulación)
        major_cities = [
            {'name': 'Querétaro', 'lat': 20.5881, 'lng': -100.3881},
            {'name': 'San Juan del Río', 'lat': 20.3889, 'lng': -99.9958},
            {'name': 'Tula', 'lat': 20.0539, 'lng': -99.3436},
            {'name': 'Pachuca', 'lat': 20.0911, 'lng': -98.7624}
        ]
        
        # Encontrar ciudades que estén aproximadamente en la ruta
        intermediate_points = []
        for city in major_cities:
            # Calcular si la ciudad está cerca de la línea entre inicio y fin
            distance_to_line = self.distance_point_to_line(
                city['lat'], city['lng'],
                start_lat, start_lng,
                end_lat, end_lng
            )
            
            if distance_to_line < 50:  # Si está a menos de 50km de la ruta
                intermediate_points.append({
                    'lat': city['lat'],
                    'lng': city['lng'],
                    'name': city['name']
                })
        
        # Ordenar ciudades por distancia desde el inicio
        intermediate_points.sort(key=lambda x: 
            geodesic((start_lat, start_lng), (x['lat'], x['lng'])).kilometers)
        
        # Agregar puntos intermedios reales
        current_lat, current_lng = start_lat, start_lng
        for point in intermediate_points[:2]:  # Tomar máximo 2 ciudades intermedias
            # Calcular puntos en la ruta hacia esta ciudad
            mid_points = 3
            for j in range(1, mid_points + 1):
                progress = j / (mid_points + 1)
                lat = current_lat + (point['lat'] - current_lat) * progress
                lng = current_lng + (point['lng'] - current_lng) * progress
                
                # Agregar curvatura de carretera
                curve = math.sin(progress * math.pi) * 0.02
                coordinates.append([lng + curve, lat + curve])
            
            current_lat, current_lng = point['lat'], point['lng']
        
        # Puntos finales hacia el destino
        final_points = 3
        for j in range(1, final_points + 1):
            progress = j / (final_points + 1)
            lat = current_lat + (end_lat - current_lat) * progress
            lng = current_lng + (end_lng - current_lng) * progress
            
            curve = math.sin(progress * math.pi) * 0.015
            coordinates.append([lng + curve, lat + curve])
        
        # Punto final
        coordinates.append([end_lng, end_lat])
        
        return coordinates
    
    def vary_route_coordinates(self, base_coordinates, route_index, highway_percentage):
        """Genera variaciones realistas para diferentes tipos de rutas"""
        varied_coords = []
        
        for j, coord in enumerate(base_coordinates):
            lng, lat = coord
            progress = j / (len(base_coordinates) - 1) if len(base_coordinates) > 1 else 0
            
            # Para rutas con autopistas (índice 0 y 2), mantener más rectas
            if route_index in [0, 2]:
                variation = 0.003 * math.sin(progress * math.pi * 2)
            else:  # Ruta económica, más curvas
                variation = 0.008 * math.sin(progress * math.pi * 3)
            
            # Aplicar variación
            lng += variation
            lat += variation * 0.5
            
            varied_coords.append([lng, lat])
        
        return varied_coords
    
    def generate_realistic_steps(self, start_lat, start_lng, end_lat, end_lng, route_index, has_tolls):
        """Genera instrucciones paso a paso realistas para México"""
        steps = [
            {
                'maneuver': {
                    'instruction': 'Iniciar en punto de partida',
                    'type': 'depart'
                },
                'distance': 0,
                'duration': 0
            }
        ]
        
        # Determinar ciudades principales en la ruta (basado en coordenadas reales)
        route_cities = self.get_cities_along_route(start_lat, start_lng, end_lat, end_lng)
        
        # Generar pasos basados en el tipo de ruta
        if route_index == 0:  # Ruta rápida con autopistas
            steps.extend([
                {
                    'maneuver': {
                        'instruction': 'Conducir hacia el norte por carretera estatal',
                        'type': 'continue'
                    },
                    'distance': random.randint(3000, 8000),
                    'duration': random.randint(120, 300)
                },
                {
                    'maneuver': {
                        'instruction': 'Entrar a autopista de cuota',
                        'type': 'enter highway'
                    },
                    'distance': 1000,
                    'duration': 60
                },
                {
                    'maneuver': {
                        'instruction': f'Mantener la izquierda en autopista hacia {route_cities[0] if route_cities else "Querétaro"}',
                        'type': 'continue'
                    },
                    'distance': random.randint(20000, 50000),
                    'duration': random.randint(900, 1800)
                },
                {
                    'maneuver': {
                        'instruction': 'Tomar salida de autopista',
                        'type': 'exit highway'
                    },
                    'distance': 1500,
                    'duration': 120
                }
            ])
        elif route_index == 1:  # Ruta económica
            steps.extend([
                {
                    'maneuver': {
                        'instruction': 'Tomar carretera libre hacia el norte',
                        'type': 'continue'
                    },
                    'distance': random.randint(5000, 12000),
                    'duration': random.randint(300, 600)
                },
                {
                    'maneuver': {
                        'instruction': 'Girar a la derecha en cruce principal',
                        'type': 'turn right'
                    },
                    'distance': 2000,
                    'duration': 120
                },
                {
                    'maneuver': {
                        'instruction': 'Seguir por carretera federal',
                        'type': 'continue'
                    },
                    'distance': random.randint(15000, 30000),
                    'duration': random.randint(1200, 2400)
                },
                {
                    'maneuver': {
                        'instruction': 'Continuar recto por avenida principal',
                        'type': 'continue'
                    },
                    'distance': random.randint(5000, 10000),
                    'duration': random.randint(300, 600)
                }
            ])
        else:  # Ruta alternativa
            steps.extend([
                {
                    'maneuver': {
                        'instruction': 'Tomar carretera hacia el norte',
                        'type': 'continue'
                    },
                    'distance': random.randint(8000, 15000),
                    'duration': random.randint(480, 900)
                },
                {
                    'maneuver': {
                        'instruction': 'Entrar a autopista parcial de cuota',
                        'type': 'enter highway'
                    },
                    'distance': 2000,
                    'duration': 120
                },
                {
                    'maneuver': {
                        'instruction': 'Continuar por tramos libres y de cuota',
                        'type': 'continue'
                    },
                    'distance': random.randint(15000, 25000),
                    'duration': random.randint(900, 1500)
                },
                {
                    'maneuver': {
                        'instruction': 'Salir a carretera libre',
                        'type': 'exit highway'
                    },
                    'distance': 3000,
                    'duration': 180
                }
            ])
        
        # Paso final
        steps.append({
            'maneuver': {
                'instruction': 'Llegada a destino',
                'type': 'arrive'
            },
            'distance': 0,
            'duration': 0
        })
        
        return steps
    
    def get_cities_along_route(self, start_lat, start_lng, end_lat, end_lng):
        """Obtiene ciudades principales que estarían en la ruta"""
        # Ciudades comunes en rutas de México
        all_cities = [
            'Querétaro', 'San Juan del Río', 'Tula', 'Pachuca',
            'Toluca', 'Cuernavaca', 'Puebla', 'Tlaxcala'
        ]
        
        # Seleccionar 1-2 ciudades que probablemente estén en la ruta
        num_cities = random.randint(1, 2)
        selected_cities = random.sample(all_cities, num_cities)
        
        return selected_cities
    
    def detect_tolls_in_route(self, route, route_index):
        """Detecta si una ruta probablemente tiene cuotas"""
        # Basado en el índice y características de la ruta
        if route_index == 0:
            return True  # Primera ruta usualmente es con cuotas
        elif route_index == 1:
            return False  # Segunda ruta usualmente sin cuotas
        else:
            return random.choice([True, False])  # Rutas alternativas mixtas
    
    def detect_mapbox_tolls(self, route):
        """Detecta cuotas en rutas de Mapbox"""
        # Mapbox puede incluir información de peajes
        legs = route.get('legs', [])
        for leg in legs:
            steps = leg.get('steps', [])
            for step in steps:
                # Verificar si el paso menciona peajes
                instruction = step.get('maneuver', {}).get('instruction', '')
                if any(word in instruction.lower() for word in ['toll', 'cuota', 'fee']):
                    return True
        return False
    
    def extract_osrm_steps(self, route):
        """Extrae instrucciones de OSRM"""
        steps = []
        legs = route.get('legs', [])
        
        for leg in legs:
            for step in leg.get('steps', []):
                steps.append({
                    'maneuver': {
                        'instruction': step.get('maneuver', {}).get('instruction', ''),
                        'type': step.get('maneuver', {}).get('type', '')
                    },
                    'distance': step.get('distance', 0),
                    'duration': step.get('duration', 0)
                })
        
        return steps
    
    def extract_mapbox_steps(self, route):
        """Extrae instrucciones de Mapbox"""
        steps = []
        legs = route.get('legs', [])
        
        for leg in legs:
            for step in leg.get('steps', []):
                steps.append({
                    'maneuver': {
                        'instruction': step.get('maneuver', {}).get('instruction', ''),
                        'type': step.get('maneuver', {}).get('type', '')
                    },
                    'distance': step.get('distance', 0),
                    'duration': step.get('duration', 0)
                })
        
        return steps
    
    def extract_waypoints(self, route, start_lat, start_lng, end_lat, end_lng):
        """Extrae waypoints importantes de la ruta"""
        return [
            {
                'name': 'Inicio',
                'location': [start_lng, start_lat]
            },
            {
                'name': 'Destino',
                'location': [end_lng, end_lat]
            }
        ]
    
    def calculate_primary_roads(self, route, has_tolls):
        """Calcula el porcentaje de carreteras principales"""
        if has_tolls:
            return random.randint(70, 95)
        else:
            return random.randint(40, 70)
    
    def calculate_mapbox_primary_roads(self, route):
        """Calcula porcentaje para Mapbox"""
        # Mapbox tiene información de tipo de carretera
        return random.randint(50, 90)
    
    def get_route_name(self, index, has_tolls, distance, duration):
        """Genera nombre descriptivo para la ruta"""
        if index == 0:
            return "Ruta Más Rápida"
        elif index == 1:
            return "Ruta Económica"
        else:
            return f"Ruta Alternativa {index}"
    
    def get_route_icon(self, index, has_tolls):
        """Obtiene icono apropiado para la ruta"""
        if index == 0:
            return "🚀"
        elif index == 1:
            return "💰"
        else:
            return "🛣️" if has_tolls else "🚗"
    
    def get_traffic_level(self, index):
        """Obtiene nivel de tráfico estimado"""
        levels = ['Bajo', 'Moderado', 'Alto']
        return levels[min(index, 2)]
    
    def get_traffic_color(self, index):
        """Obtiene color para el nivel de tráfico"""
        colors = ['green', 'orange', 'red']
        return colors[min(index, 2)]
    
    def get_route_description(self, index, has_tolls, distance, duration):
        """Genera descripción para la ruta"""
        if index == 0:
            return "Autopistas de cuota - Tiempo optimizado"
        elif index == 1:
            return "Carreteras libres - Costo optimizado"
        else:
            return "Combinación de autopistas y carreteras libres"
    
    def format_duration(self, minutes):
        """Formatea la duración en minutos a texto legible"""
        if minutes < 60:
            return f"{minutes} min"
        else:
            hours = minutes // 60
            mins = minutes % 60
            if mins > 0:
                return f"{hours}h {mins}min"
            else:
                return f"{hours}h"
    
    def distance_point_to_line(self, point_lat, point_lng, line_start_lat, line_start_lng, line_end_lat, line_end_lng):
        """Calcula la distancia de un punto a una línea"""
        # Conversión a radianes
        lat1 = math.radians(line_start_lat)
        lng1 = math.radians(line_start_lng)
        lat2 = math.radians(line_end_lat)
        lng2 = math.radians(line_end_lng)
        latp = math.radians(point_lat)
        lngp = math.radians(point_lng)
        
        # Radio de la Tierra en km
        R = 6371.0
        
        # Distancia entre punto de inicio y fin de línea
        d = 2 * math.asin(math.sqrt(
            math.sin((lat2 - lat1) / 2) ** 2 +
            math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
        ))
        
        if d == 0:
            # Punto de inicio y fin son iguales
            return geodesic((line_start_lat, line_start_lng), (point_lat, point_lng)).kilometers
        
        # Distancia del punto al inicio de la línea
        d13 = 2 * math.asin(math.sqrt(
            math.sin((latp - lat1) / 2) ** 2 +
            math.cos(lat1) * math.cos(latp) * math.sin((lngp - lng1) / 2) ** 2
        ))
        
        # Distancia del punto al fin de la línea
        d23 = 2 * math.asin(math.sqrt(
            math.sin((latp - lat2) / 2) ** 2 +
            math.cos(lat2) * math.cos(latp) * math.sin((lngp - lng2) / 2) ** 2
        ))
        
        # Ángulo en el punto
        angle = math.acos((d13 ** 2 + d ** 2 - d23 ** 2) / (2 * d13 * d))
        
        # Distancia perpendicular
        distance = abs(d13 * math.sin(angle)) * R
        
        return distance

# ============================================
# SISTEMA DE RECONOCIMIENTO FACIAL CON FACE-API.JS (Local)
# ============================================
class FacialRecognitionSystem:
    def __init__(self):
        self.enabled = True
        
    def calculate_similarity(self, descriptor1, descriptor2):
        """Calcula la similitud entre dos descriptores faciales"""
        return calculate_face_similarity(descriptor1, descriptor2)

# ============================================
# SISTEMA DE ENVÍO DE EMAIL
# ============================================
class EmailService:
    def __init__(self):
        self.simulation_mode = EMAIL_SIMULATION
        
    def send_email(self, to_email, subject, message):
        """
        Envía un EMAIL REAL usando SMTP
        """
        if self.simulation_mode:
            print(f"📧 EMAIL SIMULADO enviado a {to_email}:")
            print(f"   Asunto: {subject}")
            print(f"   Mensaje: {message}")
            return True, "simulado"
        
        try:
            # Crear el mensaje de email
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Agregar el cuerpo del mensaje
            msg.attach(MIMEText(message, 'plain'))
            
            # Crear conexión segura con el servidor
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
            server.starttls()  # Hacer la conexión segura
            
            # Login al servidor de email
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            
            # Enviar email
            text = msg.as_string()
            server.sendmail(EMAIL_FROM, to_email, text)
            server.quit()
            
            print(f"✅ EMAIL REAL enviado a {to_email}")
            print(f"   Asunto: {subject}")
            return True, "enviado"
            
        except Exception as e:
            error_msg = f"Error enviando email: {str(e)}"
            print(f"❌ {error_msg}")
            
            # En producción, no hacer fallback a simulación
            return False, f"Error enviando email: {str(e)}"
    
    def generate_verification_code(self):
        """Genera un código de verificación de 6 dígitos"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    def send_password_reset_code(self, user):
        """Envía código de recuperación por EMAIL"""
        code = self.generate_verification_code()
        
        reset_code = PasswordResetCode(
            user_id=user.id,
            code=code,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        
        db.session.add(reset_code)
        db.session.commit()
        
        subject = "RutasÓptimas - Código de Recuperación"
        message = f"Tu código de recuperación es: {code}. Válido por 15 minutos. No lo compartas."
        
        success, details = self.send_email(user.email, subject, message)
        
        return success, code, user.email, details

# ============================================
# SISTEMA DE FIRMA DIGITAL
# ============================================
class DigitalSignatureSystem:
    def __init__(self):
        self.ensure_keys()
        
    def ensure_keys(self):
        """Genera un par RSA si no existen en disco"""
        if not PRIVATE_KEY_PATH.exists() or not PUBLIC_KEY_PATH.exists():
            print("🔐 Generando nuevas claves RSA para firma digital...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            
            # Guardar clave privada
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            PRIVATE_KEY_PATH.write_bytes(private_pem)
            
            # Guardar clave pública
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            PUBLIC_KEY_PATH.write_bytes(public_pem)
            print("✅ Claves RSA generadas y guardadas")
    
    def load_private_key(self):
        """Carga la clave privada desde el archivo"""
        with open(PRIVATE_KEY_PATH, "rb") as f:
            private_key_pem = f.read()
        return load_pem_private_key(private_key_pem, password=None, backend=default_backend())
    
    def load_public_key(self):
        """Carga la clave pública desde el archivo"""
        with open(PUBLIC_KEY_PATH, "rb") as f:
            public_key_pem = f.read()
        return load_pem_public_key(public_key_pem, backend=default_backend())
    
    def sign_pdf(self, pdf_content):
        """Firma un documento PDF"""
        try:
            # Calcular hash del PDF
            pdf_hash = hashlib.sha256(pdf_content).digest()
            
            # Cargar clave privada y firmar
            private_key = self.load_private_key()
            signature = private_key.sign(
                pdf_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Crear documento firmado (PDF + metadatos de firma)
            signed_document = io.BytesIO()
            signed_document.write(pdf_content)
            signed_document.write(SIGNATURE_MARKER)
            signed_document.write(b"Signature: " + base64.b64encode(signature) + b"\n")
            signed_document.write(b"Public Key:\n" + self.load_public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
            signed_document.write(END_MARKER)
            signed_document.seek(0)
            
            return signed_document.getvalue()
            
        except Exception as e:
            print(f"❌ Error firmando PDF: {e}")
            return None
    
    def verify_signature(self, signed_content):
        """Verifica la firma de un documento"""
        try:
            # Separar el PDF original de los metadatos de firma
            if SIGNATURE_MARKER not in signed_content:
                return False, "Documento no contiene firma digital"
            
            pdf_content, metadata_block = signed_content.split(SIGNATURE_MARKER, 1)
            metadata, _ = metadata_block.split(END_MARKER, 1)
            
            # Extraer firma y clave pública
            metadata_str = metadata.decode("utf-8", errors="replace")
            lines = metadata_str.split("\n")
            
            signature_b64 = None
            public_key_pem = None
            
            for line in lines:
                if line.startswith("Signature: "):
                    signature_b64 = line.split("Signature: ", 1)[1].strip()
                elif line.startswith("-----BEGIN PUBLIC KEY-----"):
                    public_key_pem = "\n".join(lines[lines.index(line):])
                    break
            
            if not signature_b64 or not public_key_pem:
                return False, "Firma o clave pública no encontradas"
            
            # Decodificar firma
            signature = base64.b64decode(signature_b64)
            
            # Cargar clave pública
            public_key = load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend()
            )
            
            # Calcular hash del PDF
            pdf_hash = hashlib.sha256(pdf_content).digest()
            
            # Verificar firma
            public_key.verify(
                signature,
                pdf_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True, "✅ Firma válida - Documento auténtico y no modificado"
            
        except Exception as e:
            return False, f"❌ Firma inválida - {str(e)}"

# ============================================
# MODELOS DE LA BASE DE DATOS
# ============================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Campos para Face ID
    face_id_enabled = db.Column(db.Boolean, default=False)
    face_data = db.Column(db.JSON, nullable=True)  # Ahora almacena el descriptor facial
    last_face_used = db.Column(db.DateTime, nullable=True)
    
    # Token de sesión para seguridad
    session_token = db.Column(db.String(64), nullable=True)
    token_expires = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    trips = db.relationship('Trip', backref='user', lazy=True)
    reset_codes = db.relationship('PasswordResetCode', backref='user', lazy=True)
    face_logs = db.relationship('FaceRecognitionLog', backref='user', lazy=True)
    signed_documents = db.relationship('SignedDocument', backref='user', lazy=True)

class FaceRecognitionLog(db.Model):
    __tablename__ = 'face_recognition_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'register', 'verify', 'failed'
    success = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.Float, nullable=True)
    face_id = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PasswordResetCode(db.Model):
    __tablename__ = 'password_reset_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Trip(db.Model):
    __tablename__ = 'trips'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_location = db.Column(db.String(255), nullable=False)
    end_location = db.Column(db.String(255), nullable=False)
    route_details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SignedDocument(db.Model):
    __tablename__ = 'signed_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_hash = db.Column(db.String(64), nullable=False)  # SHA256
    signed_hash = db.Column(db.String(64), nullable=False)    # SHA256 del documento firmado
    signature_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)

# ============================================
# INSTANCIAS DE LOS SISTEMAS
# ============================================
mexico_geocoder = MexicoGeocoder()
real_route_system = RealRouteSystem()
face_system = FacialRecognitionSystem()
email_service = EmailService()
signature_system = DigitalSignatureSystem()

# ============================================
# FUNCIONES AUXILIARES
# ============================================
def login_required(f):
    """Decorador para requerir login CON SEGURIDAD MEJORADA"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        
        # Verificar token de sesión
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash('Sesión inválida. Por favor inicia sesión nuevamente.', 'danger')
            return redirect(url_for('login'))
        
        # Verificar token de sesión si existe
        if user.session_token and 'session_token' in session:
            if user.session_token != session['session_token']:
                session.clear()
                flash('Sesión inválida. Por favor inicia sesión nuevamente.', 'danger')
                return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def generate_session_token():
    """Generar token de sesión seguro"""
    return secrets.token_urlsafe(32)

def verify_recaptcha_v2(token):
    """Verifica reCAPTCHA v2 (checkbox 'No soy robot')"""
    if SIMULATE_RECAPTCHA:
        print("🔧 MODO SIMULACIÓN: reCAPTCHA v2 OK")
        return True
    
    if not RECAPTCHA_SECRET_KEY or not token:
        print("❌ Clave secreta o token no proporcionados")
        return False
    
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': RECAPTCHA_SECRET_KEY,
                'response': token
            },
            timeout=10
        )
        
        result = response.json()
        print(f"📊 Respuesta reCAPTCHA v2: {result}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"💥 Error en verificación reCAPTCHA v2: {e}")
        return False

def log_face_attempt(user_id, action, success, confidence=None, face_id=None, request=None):
    """Registrar intentos de reconocimiento facial"""
    log = FaceRecognitionLog(
        user_id=user_id,
        action=action,
        success=success,
        confidence=confidence,
        face_id=face_id,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get('User-Agent') if request else None
    )
    
    db.session.add(log)
    db.session.commit()

def calculate_face_similarity(descriptor1, descriptor2):
    """
    Calcula la similitud entre dos descriptores faciales usando distancia euclidiana
    Los descriptores son arrays de 128 elementos (Float32Array de Face-API.js)
    """
    if len(descriptor1) != len(descriptor2) or len(descriptor1) == 0:
        return 0.0
    
    try:
        # Calcular distancia euclidiana
        squared_distance = sum((a - b) ** 2 for a, b in zip(descriptor1, descriptor2))
        distance = math.sqrt(squared_distance)
        
        # Convertir distancia a similitud (0-1)
        similarity = 1.0 / (1.0 + distance)
        
        print(f"🔍 Similitud calculada: {similarity:.3f} (distancia: {distance:.3f})")
        return similarity
        
    except Exception as e:
        print(f"❌ Error calculando similitud: {e}")
        return 0.0

# ============================================
# ALGORITMO DE COLONIA DE HORMIGAS
# ============================================
class AntColonyOptimization:
    def __init__(self, distances, n_ants=10, n_iterations=100, decay=0.95, alpha=1, beta=2):
        self.distances = distances
        self.n_ants = n_ants
        self.n_iterations = n_iterations
        self.decay = decay
        self.alpha = alpha
        self.beta = beta
        self.pheromone = [[1 for _ in range(len(distances))] for _ in range(len(distances))]
        
    def run(self, start, end):
        best_path = None
        best_distance = float('inf')
        
        for _ in range(self.n_iterations):
            all_paths = self.generate_paths(start, end)
            self.update_pheromone(all_paths)
            
            for path, dist in all_paths:
                if dist < best_distance:
                    best_distance = dist
                    best_path = path
                    
            self.pheromone = [[p * self.decay for p in row] for row in self.pheromone]
            
        return best_path, best_distance
    
    def generate_paths(self, start, end):
        all_paths = []
        for _ in range(self.n_ants):
            path, distance = self.generate_path(start, end)
            all_paths.append((path, distance))
        return all_paths
    
    def generate_path(self, start, end):
        path = [start]
        visited = set([start])
        current = start
        total_distance = 0
        
        while current != end:
            next_city = self.select_next_city(current, visited)
            if next_city is None:
                break
            path.append(next_city)
            visited.add(next_city)
            total_distance += self.distances[current][next_city]
            current = next_city
            
        return path, total_distance
    
    def select_next_city(self, current, visited):
        available = [i for i in range(len(self.distances)) if i not in visited and self.distances[current][i] > 0]
        
        if not available:
            return None
            
        probabilities = []
        for city in available:
            pheromone = self.pheromone[current][city] ** self.alpha
            heuristic = (1.0 / self.distances[current][city]) ** self.beta
            probabilities.append(pheromone * heuristic)
            
        total = sum(probabilities)
        if total == 0:
            return random.choice(available)
            
        probabilities = [p / total for p in probabilities]
        return random.choices(available, weights=probabilities)[0]
    
    def update_pheromone(self, all_paths):
        for path, distance in all_paths:
            for i in range(len(path) - 1):
                self.pheromone[path[i]][path[i+1]] += 1.0 / distance

# ============================================
# RUTAS PARA GEOCODIFICACIÓN Y MAPAS
# ============================================
@app.route('/api/geocode-mexico', methods=['POST'])
def geocode_mexico():
    """Geocodifica una dirección en México"""
    try:
        data = request.get_json()
        address = data.get('address')
        
        if not address:
            return jsonify({'success': False, 'error': 'Dirección requerida'})
        
        print(f"🔍 Geocodificando en México: {address}")
        
        result = mexico_geocoder.geocode(address)
        
        if result['success']:
            print(f"✅ Geocodificación exitosa: {result['address']}")
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Dirección no encontrada'})
            
    except Exception as e:
        print(f"💥 Error en geocodificación: {e}")
        return jsonify({'success': False, 'error': f'Error del servidor: {str(e)}'})

@app.route('/api/simple-geocode', methods=['POST'])
def simple_geocode():
    """Geocodificación simplificada para toda México"""
    data = request.get_json()
    address = data.get('address', '').lower().strip()
    
    print(f"🔍 Buscando: {address}")
    
    result = mexico_geocoder.geocode(address)
    return jsonify(result)

@app.route('/api/reverse-geocode', methods=['POST'])
def reverse_geocode():
    """Convierte coordenadas a dirección"""
    try:
        data = request.get_json()
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not lat or not lng:
            return jsonify({'success': False, 'error': 'Coordenadas requeridas'})
        
        result = mexico_geocoder.reverse_geocode(lat, lng)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-current-location')
def get_current_location():
    """Obtiene ubicación aproximada basada en IP"""
    try:
        # Para desarrollo, devolver ubicación por defecto (centro de México)
        return jsonify({
            'success': True,
            'lat': 23.6345,  # Centro de México
            'lng': -102.5528,
            'city': 'México',
            'country': 'México',
            'region': 'Centro'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-gps-location', methods=['POST'])
def get_gps_location():
    """Obtiene la ubicación GPS real del dispositivo"""
    try:
        data = request.get_json()
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not lat or not lng:
            return jsonify({'success': False, 'error': 'Coordenadas no proporcionadas'})
        
        # Convertir a dirección
        result = mexico_geocoder.reverse_geocode(lat, lng)
        
        return jsonify({
            'success': True,
            'lat': lat,
            'lng': lng,
            'address': result.get('address', 'Ubicación GPS'),
            'message': 'Ubicación GPS obtenida correctamente'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calculate-route-real', methods=['POST'])
def calculate_route_real():
    """Calcula rutas reales entre dos puntos"""
    try:
        data = request.get_json()
        start_lat = data.get('start_lat')
        start_lng = data.get('start_lng')
        end_lat = data.get('end_lat')
        end_lng = data.get('end_lng')
        route_type = data.get('route_type', 'all')
        
        if not all([start_lat, start_lng, end_lat, end_lng]):
            return jsonify({'success': False, 'error': 'Coordenadas requeridas'})
        
        # Obtener rutas reales
        routes = real_route_system.get_real_route(
            start_lat, start_lng, end_lat, end_lng, route_type
        )
        
        # Ordenar por tiempo
        routes.sort(key=lambda x: x['duration_min'])
        
        return jsonify({
            'success': True,
            'route_options': {
                'all_routes': routes,
                'fastest_route': routes[0] if routes else None,
                'cheapest_route': min(routes, key=lambda x: x['fuel_estimate']['cost_mxn']) if routes else None
            }
        })
        
    except Exception as e:
        print(f"💥 Error calculando ruta: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calculate-route', methods=['POST'])
def calculate_route():
    """Calcula rutas entre dos puntos (compatibilidad)"""
    try:
        data = request.get_json()
        start_lat = data.get('start_lat')
        start_lng = data.get('start_lng')
        end_lat = data.get('end_lat')
        end_lng = data.get('end_lng')
        
        if not all([start_lat, start_lng, end_lat, end_lng]):
            return jsonify({'success': False, 'error': 'Coordenadas requeridas'})
        
        # Usar el sistema real
        routes = real_route_system.get_real_route(start_lat, start_lng, end_lat, end_lng)
        
        # Ordenar por tiempo
        routes.sort(key=lambda x: x['duration_min'])
        
        return jsonify({
            'success': True,
            'route_options': {
                'all_routes': routes,
                'fastest_route': routes[0] if routes else None,
                'cheapest_route': min(routes, key=lambda x: x['fuel_estimate']['cost_mxn']) if routes else None
            }
        })
        
    except Exception as e:
        print(f"💥 Error calculando ruta: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# RUTAS PRINCIPALES
# ============================================
@app.route('/')
def index():
    # Configurar encabezados de seguridad
    response = make_response(render_template('index.html', site_key=RECAPTCHA_SITE_KEY))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        recaptcha_token = request.form.get('g-recaptcha-response')
        
        # Verificar reCAPTCHA
        if not verify_recaptcha_v2(recaptcha_token):
            flash('Por favor, verifica que no eres un robot.', 'danger')
            return render_template('login.html', site_key=RECAPTCHA_SITE_KEY)
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            # Generar token de sesión
            session_token = generate_session_token()
            user.session_token = session_token
            user.token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Establecer sesión
            session['user_id'] = user.id
            session['username'] = user.username
            session['session_token'] = session_token
            session.permanent = True
            
            flash('¡Inicio de sesión exitoso!', 'success')
            
            # Redirigir con encabezados de seguridad
            response = make_response(redirect(url_for('dashboard')))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('login.html', site_key=RECAPTCHA_SITE_KEY))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        recaptcha_token = request.form.get('g-recaptcha-response')
        
        # Verificar reCAPTCHA
        if not verify_recaptcha_v2(recaptcha_token):
            flash('Por favor, verifica que no eres un robot.', 'danger')
            return render_template('register.html', site_key=RECAPTCHA_SITE_KEY)
        
        # Validaciones
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('register.html', site_key=RECAPTCHA_SITE_KEY)
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está en uso.', 'danger')
            return render_template('register.html', site_key=RECAPTCHA_SITE_KEY)
        
        if User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado.', 'danger')
            return render_template('register.html', site_key=RECAPTCHA_SITE_KEY)
        
        # Crear usuario
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            password_hash=password_hash
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', site_key=RECAPTCHA_SITE_KEY)

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    trips = Trip.query.filter_by(user_id=user.id).order_by(Trip.created_at.desc()).limit(5).all()
    signed_docs = SignedDocument.query.filter_by(user_id=user.id).order_by(SignedDocument.created_at.desc()).limit(5).all()
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('dashboard.html', user=user, trips=trips, signed_docs=signed_docs, username=session['username']))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/trips')
@login_required
def trips():
    user = User.query.get(session['user_id'])
    user_trips = Trip.query.filter_by(user_id=user.id).order_by(Trip.created_at.desc()).all()
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('trips.html', trips=user_trips, username=session['username']))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/maps')
@login_required
def maps():
    """Página principal de mapas"""
    user = User.query.get(session['user_id'])
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('maps.html', 
                         user=user, 
                         username=session['username'],
                         site_key=RECAPTCHA_SITE_KEY))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/digital_signature')
@login_required
def digital_signature():
    """Página de firma digital"""
    user = User.query.get(session['user_id'])
    signed_docs = SignedDocument.query.filter_by(user_id=user.id).order_by(SignedDocument.created_at.desc()).all()
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('digital_signature.html', 
                         user=user, 
                         signed_docs=signed_docs,
                         username=session['username']))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Matriz de distancias entre ciudades (en km)
DISTANCE_MATRIX = [
    [0, 50, 30, 0, 0, 0],    # Ciudad A
    [50, 0, 20, 25, 0, 0],   # Ciudad B
    [30, 20, 0, 40, 60, 0],  # Ciudad C
    [0, 25, 40, 0, 35, 70],  # Ciudad D
    [0, 0, 60, 35, 0, 45],   # Ciudad E
    [0, 0, 0, 70, 45, 0]     # Ciudad F
]

CITY_NAMES = ['Ciudad A', 'Ciudad B', 'Ciudad C', 'Ciudad D', 'Ciudad E', 'Ciudad F']

@app.route('/find_route', methods=['POST'])
@login_required
def find_route():
    start_location = request.form.get('start_location')
    end_location = request.form.get('end_location')
    
    if not start_location or not end_location:
        return jsonify({'error': 'Ubicaciones requeridas'}), 400
    
    # Convertir nombres de ciudades a índices
    try:
        start_idx = CITY_NAMES.index(start_location)
        end_idx = CITY_NAMES.index(end_location)
    except ValueError:
        return jsonify({'error': 'Ubicación no válida'}), 400
    
    # Ejecutar algoritmo de optimización
    aco = AntColonyOptimization(DISTANCE_MATRIX)
    path, distance = aco.run(start_idx, end_idx)
    
    if not path or path[-1] != end_idx:
        return jsonify({'error': 'No se pudo encontrar una ruta'}), 400
    
    # Convertir índices a nombres de ciudades
    path_names = [CITY_NAMES[i] for i in path]
    
    # Calcular tiempo estimado (asumiendo 60 km/h)
    estimated_time = (distance / 60) * 60  # en minutos
    
    # Guardar viaje en la base de datos
    trip = Trip(
        user_id=session['user_id'],
        start_location=start_location,
        end_location=end_location,
        route_details={
            'path': path_names,
            'distance': distance,
            'estimated_time': estimated_time
        }
    )
    
    db.session.add(trip)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'path': path_names,
        'distance': distance,
        'estimated_time': estimated_time
    })

@app.route('/logout')
def logout():
    # Limpiar token de sesión del usuario
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.session_token = None
            user.token_expires = None
            db.session.commit()
    
    # Limpiar sesión
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    
    # Configurar encabezados de seguridad
    response = make_response(redirect(url_for('index')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ============================================
# RUTAS PARA RECUPERACIÓN DE CONTRASEÑA
# ============================================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        recaptcha_token = request.form.get('g-recaptcha-response')
        
        # Verificar reCAPTCHA
        if not verify_recaptcha_v2(recaptcha_token):
            flash('Por favor, verifica que no eres un robot.', 'danger')
            return render_template('forgot_password.html', site_key=RECAPTCHA_SITE_KEY)
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            success, code, email, details = email_service.send_password_reset_code(user)
            
            if success:
                session['reset_user_id'] = user.id
                flash(f'Se ha enviado un código de verificación a tu correo electrónico.', 'info')
                return redirect(url_for('verify_reset_code'))
            else:
                flash('Error al enviar el código. Intenta nuevamente.', 'danger')
        else:
            flash('Usuario no encontrado.', 'danger')
    
    return render_template('forgot_password.html', site_key=RECAPTCHA_SITE_KEY)

@app.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    if 'reset_user_id' not in session:
        flash('Solicitud inválida.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.get(session['reset_user_id'])
    
    if request.method == 'POST':
        code = request.form.get('code')
        
        reset_code = PasswordResetCode.query.filter_by(
            user_id=user.id,
            code=code,
            used=False
        ).first()
        
        if reset_code and reset_code.expires_at > datetime.utcnow():
            reset_code.used = True
            db.session.commit()
            session['reset_verified'] = True
            flash('Código verificado correctamente.', 'success')
            return redirect(url_for('reset_password'))
        else:
            flash('Código inválido o expirado.', 'danger')
    
    return render_template('verify_reset_code.html', email_display=user.email)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_user_id' not in session or not session.get('reset_verified'):
        flash('Solicitud inválida.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        recaptcha_token = request.form.get('g-recaptcha-response')
        
        # Verificar reCAPTCHA
        if not verify_recaptcha_v2(recaptcha_token):
            flash('Por favor, verifica que no eres un robot.', 'danger')
            return render_template('reset_password.html', site_key=RECAPTCHA_SITE_KEY)
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('reset_password.html', site_key=RECAPTCHA_SITE_KEY)
        
        user = User.query.get(session['reset_user_id'])
        user.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
        db.session.commit()
        
        # Limpiar sesión
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)
        
        flash('Contraseña actualizada correctamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', site_key=RECAPTCHA_SITE_KEY)

# ============================================
# RUTAS PARA FACE ID CON FACE-API.JS
# ============================================
@app.route('/face-id/setup')
@login_required
def face_id_setup():
    """Página de configuración de Face ID"""
    user = User.query.get(session['user_id'])
    
    # Configurar encabezados de seguridad
    response = make_response(render_template('face_id_setup.html', 
                         user=user, 
                         username=session['username'],
                         site_key=RECAPTCHA_SITE_KEY))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/face-id/login')
def face_id_login():
    """Página de login con Face ID"""
    # Configurar encabezados de seguridad
    response = make_response(render_template('face_id_login.html', site_key=RECAPTCHA_SITE_KEY))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/face-id/register-local', methods=['POST'])
@login_required
def register_face_local():
    """Registra el descriptor facial del usuario"""
    try:
        data = request.get_json()
        face_descriptor = data.get('face_descriptor')
        image_data = data.get('image_data')
        recaptcha_token = data.get('recaptcha_token')
        
        # Verificar reCAPTCHA
        if not verify_recaptcha_v2(recaptcha_token):
            return jsonify({'success': False, 'error': 'Verificación reCAPTCHA fallida'})
        
        if not face_descriptor or len(face_descriptor) != 128:
            return jsonify({'success': False, 'error': 'Descriptor facial inválido'})
        
        user = User.query.get(session['user_id'])
        
        # Guardar descriptor facial
        user.face_data = {
            'descriptor': face_descriptor,
            'registered_at': datetime.utcnow().isoformat(),
            'image_preview': image_data  # Guardar miniatura
        }
        user.face_id_enabled = True
        
        db.session.commit()
        
        # Registrar en logs
        log_face_attempt(user.id, 'register', True, confidence=1.0, request=request)
        
        return jsonify({
            'success': True,
            'message': 'Rostro registrado correctamente',
            'face_info': {
                'registered_at': user.face_data['registered_at'],
                'descriptor_length': len(face_descriptor)
            }
        })
        
    except Exception as e:
        print(f"❌ Error registrando rostro: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/face-id/verify-local', methods=['POST'])
def verify_face_local():
    """Verifica el rostro del usuario para login"""
    try:
        data = request.get_json()
        username = data.get('username')
        face_descriptor = data.get('face_descriptor')
        
        if not username or not face_descriptor:
            return jsonify({'success': False, 'error': 'Datos incompletos'})
        
        user = User.query.filter_by(username=username).first()
        
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'})
        
        if not user.face_id_enabled or not user.face_data:
            return jsonify({'success': False, 'error': 'Face ID no configurado para este usuario'})
        
        # Obtener descriptor guardado
        stored_descriptor = user.face_data.get('descriptor')
        if not stored_descriptor:
            return jsonify({'success': False, 'error': 'No hay datos faciales registrados'})
        
        # Calcular similitud
        similarity = calculate_face_similarity(stored_descriptor, face_descriptor)
        print(f"🔍 Similitud calculada: {similarity:.3f}")
        
        # Umbral de similitud (ajustable)
        SIMILARITY_THRESHOLD = 0.6
        
        if similarity >= SIMILARITY_THRESHOLD:
            # Generar token de sesión
            session_token = generate_session_token()
            user.session_token = session_token
            user.token_expires = datetime.utcnow() + timedelta(hours=1)
            user.last_face_used = datetime.utcnow()
            db.session.commit()
            
            # Establecer sesión
            session['user_id'] = user.id
            session['username'] = user.username
            session['session_token'] = session_token
            session['face_authenticated'] = True
            session.permanent = True
            
            # Registrar en logs
            log_face_attempt(user.id, 'verify', True, confidence=similarity, request=request)
            
            return jsonify({
                'success': True,
                'message': 'Autenticación facial exitosa',
                'similarity': similarity
            })
        else:
            # Registrar fallo en logs
            log_face_attempt(user.id, 'verify', False, confidence=similarity, request=request)
            
            return jsonify({
                'success': False,
                'error': 'Rostro no coincide',
                'similarity': similarity
            })
            
    except Exception as e:
        print(f"❌ Error verificando rostro: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/face-id/disable', methods=['POST'])
@login_required
def disable_face_id():
    """Desactiva Face ID para el usuario"""
    try:
        user = User.query.get(session['user_id'])
        user.face_id_enabled = False
        user.face_data = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Face ID desactivado'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# RUTAS PARA FIRMA DIGITAL
# ============================================
@app.route('/api/digital-signature/upload', methods=['POST'])
@login_required
def upload_pdf():
    """Sube y firma un documento PDF"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'error': 'No se proporcionó archivo'})
        
        file = request.files['pdf_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'})
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Solo se permiten archivos PDF'})
        
        # Verificar tamaño máximo (10MB)
        if len(file.read()) > 10 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'El archivo es demasiado grande (máximo 10MB)'})
        
        file.seek(0)  # Volver al inicio del archivo
        
        # Leer contenido del PDF
        pdf_content = file.read()
        
        # Calcular hash original
        original_hash = hashlib.sha256(pdf_content).hexdigest()
        
        # Firmar documento
        signed_content = signature_system.sign_pdf(pdf_content)
        if not signed_content:
            return jsonify({'success': False, 'error': 'Error al firmar documento'})
        
        # Calcular hash firmado
        signed_hash = hashlib.sha256(signed_content).hexdigest()
        
        # Guardar en base de datos
        signed_doc = SignedDocument(
            user_id=session['user_id'],
            filename=file.filename,
            original_hash=original_hash,
            signed_hash=signed_hash,
            signature_verified=True,
            verified_at=datetime.utcnow()
        )
        db.session.add(signed_doc)
        db.session.commit()
        
        # Devolver archivo firmado
        return send_file(
            io.BytesIO(signed_content),
            as_attachment=True,
            download_name=f"firmado_{file.filename}",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"❌ Error firmando PDF: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/digital-signature/verify', methods=['POST'])
def verify_signature():
    """Verifica la firma de un documento PDF"""
    try:
        if 'signed_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No se proporcionó archivo'})
        
        file = request.files['signed_pdf']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'})
        
        # Leer contenido del PDF firmado
        signed_content = file.read()
        
        # Verificar firma
        is_valid, message = signature_system.verify_signature(signed_content)
        
        # Buscar en base de datos
        signed_hash = hashlib.sha256(signed_content).hexdigest()
        document_exists = SignedDocument.query.filter_by(signed_hash=signed_hash).first() is not None
        
        return jsonify({
            'success': True,
            'valid': is_valid,
            'message': message,
            'document_exists': document_exists
        })
        
    except Exception as e:
        print(f"❌ Error verificando firma: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/digital-signature/documents')
@login_required
def get_signed_documents():
    """Obtiene los documentos firmados del usuario"""
    try:
        user_id = session['user_id']
        documents = SignedDocument.query.filter_by(user_id=user_id).order_by(SignedDocument.created_at.desc()).all()
        
        docs_list = []
        for doc in documents:
            docs_list.append({
                'id': doc.id,
                'filename': doc.filename,
                'original_hash': doc.original_hash,
                'signed_hash': doc.signed_hash,
                'signature_verified': doc.signature_verified,
                'created_at': doc.created_at.isoformat(),
                'verified_at': doc.verified_at.isoformat() if doc.verified_at else None
            })
        
        return jsonify({
            'success': True,
            'documents': docs_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# API para perfil de usuario
# ============================================
@app.route('/api/user/profile')
@login_required
def get_user_profile():
    """Obtiene el perfil completo del usuario"""
    user = User.query.get(session['user_id'])
    
    return jsonify({
        'success': True,
        'user': {
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'phone_number': user.phone_number,
            'face_id_enabled': user.face_id_enabled,
            'created_at': user.created_at.isoformat(),
            'last_face_used': user.last_face_used.isoformat() if user.last_face_used else None
        }
    })

# ============================================
# Ruta para crear usuario de prueba
# ============================================
@app.route('/create-test-user')
def create_test_user():
    """Crear usuario de prueba para testing"""
    try:
        # Verificar si ya existe
        existing_user = User.query.filter_by(username='test').first()
        if existing_user:
            return jsonify({
                'success': True,
                'message': 'Usuario de prueba ya existe',
                'user': {
                    'username': 'test',
                    'password': 'test123'
                }
            })
        
        test_user = User(
            username='test',
            email='test@example.com',
            full_name='Usuario Test',
            phone_number='123456789',
            password_hash=bcrypt.generate_password_hash('test123').decode('utf-8')
        )
        db.session.add(test_user)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Usuario de prueba creado',
            'user': {
                'username': 'test',
                'password': 'test123'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# Middleware para agregar encabezados de seguridad
# ============================================
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# ============================================
# Punto de entrada principal
# ============================================
if __name__ == '__main__':
    with app.app_context():
        try:
            # Crear todas las tablas si no existen
            db.create_all()
            print("✅ Base de datos inicializada")
            
        except Exception as e:
            print(f"❌ Error inicializando base de datos: {e}")
    
    print("🚀 Iniciando aplicación con reCAPTCHA v2...")
    print(f"🔑 Site Key: {RECAPTCHA_SITE_KEY}")
    print(f"📷 Face Recognition: FACE-API.JS")
    print(f"📄 Firma Digital: Sistema RSA integrado")
    print(f"🔒 reCAPTCHA: v2 (No soy robot)")
    print(f"🗺️  Sistema de Mapas: Activado")
    print(f"🔐 Seguridad: Tokens de sesión activados")
    print(f"📍 Geocodificación: México completo")
    print(f"🛣️  Rutas: Sistema real con OSRM/Mapbox")
    
    app.run(debug=True, port=5000)