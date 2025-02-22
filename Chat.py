import http
import json
from langchain_core.tools import tool
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
import requests
from urllib.parse import quote
import traceback
import sqlite3
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.messages import AIMessage
from langsmith import utils
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph, END
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.tools import StructuredTool
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")
os.environ["LANGCHAIN_API_KEY"]=os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
#LANGSMITH_ENDPOINT=os.getenv("LANGSMITH_ENDPOINT")


###################################
class HotelSearchAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "booking-com15.p.rapidapi.com"
        self.headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': self.base_url
        }
    
    def search_destination(self, city: str) -> list[str]:
        """
        Search for all destination IDs using city name
        
        Args:
            city: Name of the city to search
            
        Returns:
            List of dest_ids found for the city
        """
        try:
            conn = http.client.HTTPSConnection(self.base_url)
            encoded_city = quote(city)
            
            conn.request("GET", f"/api/v1/hotels/searchDestination?query={encoded_city}", 
                        headers=self.headers)
            
            res = conn.getresponse()
            data = json.loads(res.read().decode("utf-8"))
            
            dest_ids = []
            if data.get('status') and data.get('data'):
                # Collect all destination IDs related to the city
                for location in data['data']:
                    # Include both city and district level destinations
                    if location.get('dest_type') in ['city', 'district']:
                        dest_ids.append(location['dest_id'])
                        print(f"Found {location['dest_type']} destination: {location['name']} (ID: {location['dest_id']})")
            
            if not dest_ids:
                print(f"No destination IDs found for {city}")
            
            return dest_ids
            
        except Exception as e:
            print(f"Error searching destination: {str(e)}")
            return []
    
    def search_hotels(
        self,
        city: str,
        arrival_date: str,
        departure_date: str,
        adults: int,
        children: int = 0,
        rooms: int = 1,
        min_rating: float = 0.0
    ) -> Optional[Dict]:
        """
        Search for hotels in a city across all destination IDs
        """
        try:
            dest_ids = self.search_destination(city)
            if not dest_ids:
                return None
            
            all_results = []
            
            # Search hotels for each destination ID
            for dest_id in dest_ids:
                conn = http.client.HTTPSConnection(self.base_url)
                
                # Build query parameters
                params = {
                    "dest_id": dest_id,
                    "search_type": "CITY",
                    "adults": str(adults),
                    "children_age": ",".join(['0'] * children),
                    "room_qty": str(rooms),
                    "arrival_date": arrival_date,
                    "departure_date": departure_date,
                    "units": "metric",
                    "currency_code": "AED"
                }
                
                params_str = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
                
                print(f"Searching hotels for destination ID {dest_id}...")
                
                conn.request("GET", f"/api/v1/hotels/searchHotels?{params_str}", 
                            headers=self.headers)
                
                res = conn.getresponse()
                data = json.loads(res.read().decode("utf-8"))
                
                if not data.get('status'):
                    print(f"API Error for dest_id {dest_id}: {data.get('message', 'Unknown error')}")
                    continue
                    
                hotels = data.get('data', {}).get('hotels', [])
                print(f"Found {len(hotels)} hotels for destination ID {dest_id}")
                
                # Format and filter results
                for hotel in hotels:
                    property_data = hotel.get('property', {})
                    if property_data.get('reviewScore', 0) >= min_rating:
                        all_results.append({
                            'name': property_data.get('name'),
                            'rating': property_data.get('reviewScore'),
                            'rating_word': property_data.get('reviewScoreWord'),
                            'description': hotel.get('accessibilityLabel', ''),
                            'image_url': property_data.get('photoUrls', [''])[0],
                            'price': {
                                'original': property_data.get('priceBreakdown', {}).get('strikethroughPrice', {}).get('value'),
                                'current': property_data.get('priceBreakdown', {}).get('grossPrice', {}).get('value'),
                                'currency': property_data.get('currency')
                            },
                            'location': {
                                'latitude': property_data.get('latitude'),
                                'longitude': property_data.get('longitude'),
                                'distance_to_center': property_data.get('distanceFromCenter', 'N/A')
                            }
                        })
            
            # Sort results by price
            all_results.sort(key=lambda x: x['price']['current'] if x['price']['current'] else float('inf'))
            
            return {'hotels': all_results}

        except Exception as e:
            print(f"Error searching hotels: {str(e)}")
            print(f"Full error: {traceback.format_exc()}")
            return None

    def format_results(self, results: Dict) -> None:
        """Print formatted hotel results"""
        if not results or not results.get('hotels'):
            print("No results to display")
            return
            
        print(f"\n🏨 Found {len(results['hotels'])} Available Hotels:\n")
        for idx, hotel in enumerate(results['hotels'], 1):
            print(f"Option {idx}:")
            print(f"Name: {hotel['name']}")
            print(f"Rating: {hotel['rating']} - {hotel['rating_word']}")
            print(f"Description: {hotel['description'][:200]}...")
            print(f"Price: {hotel['price']['current']} {hotel['price']['currency']}")
            if hotel['price'].get('original'):
                print(f"Original Price: {hotel['price']['original']} {hotel['price']['currency']}")
            print(f"Location: {hotel['location']['distance_to_center']} from center")
            print(f"Image: {hotel['image_url']}")
            print("-" * 80 + "\n")

###################################

class TourPackageAPI:
    def __init__(self, db_path: str = "tour_packages.db"):
        self.db_path = db_path
    
    def search_packages(self, location: Optional[str] = None, duration: Optional[int] = None, price: Optional[float] = None, destination_type: Optional[str] = None) -> Optional[Dict]:
        """
        Search for tour packages based on given criteria
        
        Args:
            location: Name of the location/destination (str)
            duration: Number of days for the tour (int, optional)
            price: Maximum price for the tour (float, optional)
            destination_type: Type of destination (str, optional)
            
        Returns:
            Dictionary containing matching tour packages
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    id,
                    location,
                    trip_id,
                    package_name,
                    url,
                    duration,
                    tour_type,
                    cities_included,
                    price,
                    created_at,
                    itinerary_data,
                    destination_type,
                    hotel
                FROM tour_packages
                WHERE 1=1
            """
            params = []
            
            if location :
                query += " AND LOWER(Location) LIKE LOWER(?)"
                params.append(f"%{location}%")
                
            if price is not None:
                query += " AND Price <= ?"
                params.append(price)
                
            if duration:
                query += " AND Duration = ?"
                params.append(duration)
            
            if destination_type:
                query += " AND destination_type = ?"
                params.append(destination_type)

            cursor.execute(query, params)
            results = cursor.fetchall()
            
            packages = []
            for row in results:
                packages.append({
                    'id': row[0],
                    'location': row[1],
                    'trip_id': row[2],
                    'package_name': row[3],
                    'url': row[4],
                    'duration': row[5],
                    'tour_type': row[6],
                    'cities_included': row[7].split('|') if row[7] else [],
                    'price': row[8],
                    'created_at': row[9],
                    'itinerary_data': row[10],
                    'destination_type': row[11],
                    'hotel': row[12]
                })
            
            conn.close()
            return {'packages': packages}
            
        except Exception as e:
            print(f"Error searching tour packages: {str(e)}")
            return None

    def format_results(self, results: Dict) -> None:
        """Print formatted tour package results"""
        if not results or not results.get('packages'):
            print("No tour packages found matching your criteria")
            return
            
        # print(f"\n🎯 Found {len(results['packages'])} Tour Packages:\n")
        # for idx, package in enumerate(results['packages'], 1):
        #     print(f"Package {idx}:")
        #     print(f"Package Name: {package['package_name']}")
        #     print(f"Location: {package['location']}")
        #     print(f"Tour Type: {package['tour_type']}")
        #     print(f"Duration: {package['duration']} days")
        #     print(f"Price: ${package['price']}")
        #     print(f"Cities Included: {', '.join(package['cities_included'])}")
        #     print(f"Trip ID: {package['trip_id']}")
        #     print(f"URL: {package['url']}")
        #     print(f"Created At: {package['created_at']}")
        #     print(f"Itinerary Data: {package['itinerary_data']}")
        #     print(f"Destination Type: {package['destination_type']}")
        #     print(f"Hotel: {package['hotel']}")
        #     print("-" * 80 + "\n")

########################################################
class StateManager:
    _current_state = None

    @classmethod
    def set_state(cls, state):
        cls._current_state = state

    @classmethod
    def get_state(cls):
        return cls._current_state

def write_to_database(data):
    """Write the customer details and booking information to the database and send confirmation email"""
    # Wrap single dictionary in a list if it's not already a list
    if not isinstance(data, list):
        data = [data]
    
    try:
        # Database operations
        conn = sqlite3.connect("BookingInfo.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tour_packages (
                Cust_id INTEGER PRIMARY KEY AUTOINCREMENT,
                Customer_name TEXT,
                Customer_email TEXT,
                Customer_mobile TEXT,
                Package_name TEXT,
                Package_id TEXT,       
                Trip_Start_date TEXT,
                Origin_city TEXT,
                Tot_adults INTEGER,
                Tot_children INTEGER,
                Tot_cost TEXT,
                Hotel_bookings TEXT
            )
        ''')

        current_state = StateManager.get_state()
        
        # Send email for each package booking
        sender_email = os.getenv("SMTP_EMAIL")
        sender_password = os.getenv("SMTP_PASSWORD")
        
        if current_state and current_state.get("user_email"):
            try:
                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = current_state.get("user_email")
                msg['Subject'] = "Your BlingDestinations Tour Package Confirmation"
                
                email_body = f"""
                Dear {current_state.get('user_name', 'Valued Customer')},
                
                Thank you for booking with BlingDestinations! Here are your trip details:
                
                BOOKING DETAILS:
                """
                for package in data:
                    # Convert hotel_bookings dictionary to JSON string if it exists
                    print("Data: ", package)
                    hotel_bookings_json = json.dumps(package.get('Hotel_bookings', {})) if package.get('Hotel_bookings') else None
                    
                    # Database insert
                    cursor.execute('''
                        INSERT INTO tour_packages 
                        (Customer_name, Customer_email, Customer_mobile, Package_name, Package_id, 
                        Trip_Start_date, Origin_city, Tot_adults, Tot_children, Tot_cost, Hotel_bookings)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        current_state.get("user_name"),
                        current_state.get("user_email"),
                        current_state.get("user_mobile"),
                        package['Package_name'],
                        package['Package_id'],
                        package['Trip_Start_date'],
                        package['Origin_city'],
                        package['Tot_adults'],
                        package.get('Tot_children', 0),
                        package['Tot_cost'],
                        hotel_bookings_json
                    ))
                    
                    # Add package details to email
                    email_body += f"""
                    TOUR PACKAGE:
                    Package Name: {package['Package_name']}
                    Package ID: {package['Package_id']}
                    Trip Start Date: {package['Trip_Start_date']}
                    Origin City: {package['Origin_city']}
                    Number of Adults: {package['Tot_adults']}
                    Number of Children: {package.get('Tot_children', 0)}
                    Total Cost: {package['Tot_cost']}
                    """
                    
                    # Add hotel booking details if any
                    if hotel_bookings_json:
                        hotel_bookings = json.loads(hotel_bookings_json)
                        email_body += "\nHOTEL BOOKINGS:\n"
                        for hotel in hotel_bookings.values():
                            email_body += f"""
                            Hotel Name: {hotel.get('name')}
                            Check-in: {hotel.get('check_in')}
                            Check-out: {hotel.get('check_out')}
                            Price per Night: {hotel.get('price', 'N/A')}
                            """
                
                email_body += f"""
                
                For any queries or assistance, please feel free to contact us.
                
                Best Regards,
                BlingDestinations Team
                """
                
                msg.attach(MIMEText(email_body, 'plain'))
                print("Email body: ", email_body)
                # Send email
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.send_message(msg)
                
            except Exception as e:
                print(f"Error sending confirmation email: {str(e)}")
                # Continue with database operations even if email fails
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error in database operation: {str(e)}")
        return False

#########################################################
prompt1 = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            '''You manage the front desk for a reputed tour management agency based in India, BlingDestinations,  that caters to high profile clientele. 
               You are a seasoned travel planner, with exceptional ability to work with customers with utmost patience and politeness in understanding their vacation travel plans.
               Your responsibility is to take inputs from customers about their interests and preferences (like destination, duration, type of destination (Beach/Island, Wildlife/Nature, 
               Culture, Heritage, Shopping, Other), and help them finalize the tour plan.
               The information about the tour packages can be accessed using the search_packages tool. Only the packages that are part of the search_packages tool should be proposed to customer
               You can call the search packages tool giving the following arguments: location (City, Country or Region), destination_type (Beach/Island, Wildlife/Nature, Culture, Heritage, 
               Shopping, Other), duration (approximate number of days), price (Maximum price per person). Do not leave arguments blank when making search packages tool call
               - Do not use both location and destination_type arguments together in the search_packages tool call. Location is more specific and destination_type is more general.
               The search_packages tool will return a list of packages that match the search criteria. 
               From the list of packages, propose the packages that best fit customer's preferences (It has other details like  tour type (value, premium, standard), cities included, 
               destination_type, and itinerary data (which can be used to propose the packages)
               Share the package name, cities included, price per person, duration, tour type, destination_type, hotels: Included/Not Included, View details link (url)
               When customers ask about itinerary of a package, share the details from 'itinerary_data' for the specific itinerary, Do not respond with generic information.
               Flow of conversation:
               - Keep the welcome message short (3-4 sentences). Ask how you could help them 
               - While asking for preferences be sure to mention that you offer a wide range of options and you would be happy to help them finalize the trip within any required budget
               - In the initial part of the conversation, focus only on finalizing the destination (from the list of destinations provided by the search_packages tool) and inform them of 
                 itinerary.
               - Once destination and itineary are finalized, you need to ask get the tentative date of travel, origin city, details about the travellers 
                 (no.of adults, children/infants) for moving forward with the travel arrangements.
               - If the selected itinerary does not include hotel accommodation (indicated by 'Not Included' or 'Included' status in 'hotel' column of tour package table), ask customer 
                 if they want you to help with booking the hotel. If they are interested inform the customer that you will get back shortly after checking hotel availability details 
                 and call search_hotels tool (with appropriate search_params format) for gathering hotel details and call Search_hotels_tool to get the hotel availability details.
                    - Once you receive the hotel search results, Inform the customer of first, second, third cheapest options (as best priced options) and the best rated options,
                      along with information like Hotel name, location and facilities, price and display the pictures. Ask the customer's choice for the hotel.
                    - When there are multiple cities included in the itinerary, do this for all the cities.
                    - Once all the hotels are finalized, inform that you will be proceeding with the booking and they will be receiving confirmation and payment links via email. 
               - Once the tour package, and hotel bookings are confirmed, Share all these details (package name, cities included, duration, start date of trip, Total cost of trip 
               (Calculate total cost of the trip as: Tour package Price per person * (no.of adults + no.of children) + (Hotel Accommodation cost per Night * No.of Nights) 
               for each hotel [if hotel accommodation had been booked seprately]) 
                 list of the all the hotels selected by customer along with checkin and checkout dates) in a summary message
               - Once the chat is complete, call the write_to_database tool with the customer details and booking information to update the database without fail! Do not include 
                 Name, Customer_email and Customer_mobile in the arguments.
               - If the questions asked are not related to the travel plans, politely inform them that you are not able to answer that question.
            ''',
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

class SearchPackagesParams(BaseModel):
    location: Optional[str] = Field(None, description="Name of the destination")
    duration: Optional[int] = Field(None, description="Number of days for the tour")
    price: Optional[float] = Field(None, description="Maximum price per person")
    destination_type: Optional[str] = Field(None, description="Type of destination (Beach/Island, Wildlife/Nature, etc.)")

class WriteToDatabaseParams(BaseModel):
    #Customer_name: str = Field(..., description="Name of the Customer")
    Package_name: str = Field(..., description="Name of the Package")
    Package_id: str = Field(..., description="Package ID")
    Trip_Start_date: str = Field(..., description="Start date of the trip")
    Origin_city: str = Field(..., description="Origin city of the trip")
    Tot_adults: int = Field(..., description="Number of adults in the trip")
    Tot_children: Optional[int] = Field(None, description="Number of children in the trip")
    Tot_cost: str = Field(..., description="Total cost of the trip")
    Hotel_bookings: Optional[str] = Field(None, description="Details of the hotel bookings (Hotel name, check in date, check out date)")

#Initiating LLM Model

model = ChatOpenAI(model = 'gpt-4o-mini', temperature=0.1)

class State(MessagesState):    # First define State
    trip_details: Optional[Dict] = None
    user_email: Optional[str] = None
    user_mobile: Optional[str] = None
    user_name: Optional[str] = None


TripPlan = StateGraph(State)   # Then use State

hotel_api = HotelSearchAPI(api_key=os.getenv("RAPIDAPI_KEY"))

search_hotels_tool = StructuredTool.from_function(
    name="search_hotels",
    description="Search for hotels in a city with given details.",
    func=hotel_api.search_hotels,
)

tour_package_api = TourPackageAPI()
search_packages_tool = StructuredTool.from_function(
    name="search_packages",
    description="Search for available tour packages based on location, tour type, price, and duration. Returns package details including package name, cities included, URL, and more.",
    func=tour_package_api.search_packages,
    args_schema=SearchPackagesParams
)

DB_update_tool = StructuredTool.from_function(
    name="write_to_database",
    description="Write the customer details and booking information to the database",
    func=lambda **params: write_to_database({**params}),
    args_schema=WriteToDatabaseParams
)

tools = [search_hotels_tool, search_packages_tool, DB_update_tool]  # Register the tools
model_with_tools = model.bind_tools(tools, parallel_tool_calls=False)

def call_model(state: State):
    # Store the current state
    StateManager.set_state(state)
    
    model_with_message = prompt1.format_messages(messages=state["messages"])
    response = model_with_tools.invoke(model_with_message)
    
    return {
        "messages": [response],
        "user_email": state.get("user_email"),
        "user_mobile": state.get("user_mobile")
    }

TripPlan.add_node("model", call_model)
TripPlan.add_node("tools", ToolNode(tools))

TripPlan.add_edge(START, "model")
TripPlan.add_conditional_edges(
    "model",
    tools_condition,
)
TripPlan.add_edge("tools", "model")
memory = MemorySaver()
TravelAssistant = TripPlan.compile(checkpointer=memory)

# Modify the main block to allow importing without running the chat
if __name__ == "__main__":
    # chat()  # Comment this out
    pass

