import os
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyscreen.settings')
django.setup()

from api.models import FoodItem

def populate():
    print("Clearing existing food items...")
    FoodItem.objects.all().delete()

    print("Adding new food items with images and prices...")
    food_data = [
        {
            "name": "Samosa",
            "description": "Crispy golden fried pastry filled with spiced potatoes and peas.",
            "price": 99.00,
            "image_url": "https://images.unsplash.com/photo-1601050690597-df056fb4ce78?w=500&auto=format&fit=crop&q=60"
        },
        {
            "name": "Veg Sandwich",
            "description": "Fresh garden vegetable sandwich with green chutney and butter.",
            "price": 129.00,
            "image_url": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=500&auto=format&fit=crop&q=60"
        },
        {
            "name": "Small Salted Popcorn",
            "description": "Classic salted hot-popped popcorn.",
            "price": 199.00,
            "image_url": "https://images.unsplash.com/photo-1585647347483-22b66260dfff?w=500&auto=format&fit=crop&q=60"
        },
        {
            "name": "Veg Sandwich Combo",
            "description": "Veg Sandwich paired with a refreshing beverage.",
            "price": 220.00,
            "image_url": "https://images.unsplash.com/photo-1538220856186-0be0c085984d?w=500&auto=format&fit=crop&q=60"
        },
        {
            "name": "Pepsi Cyber-Can",
            "description": "Chilled carbonated soft drink.",
            "price": 90.00,
            "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=500&auto=format&fit=crop&q=60"
        },
        {
            "name": "Mineral Water Can",
            "description": "Packaged purified drinking water.",
            "price": 50.00,
            "image_url": "https://images.unsplash.com/photo-1560344005-7258a624d1cd?w=500&auto=format&fit=crop&q=60"
        }
    ]

    for item in food_data:
        food = FoodItem.objects.create(
            name=item["name"],
            description=item["description"],
            price=item["price"],
            image_url=item["image_url"]
        )
        print(f"Added: {food.name} - INR {food.price}")

    print("Food item population complete!")

if __name__ == '__main__':
    populate()
