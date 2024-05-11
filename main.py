from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import db_helper
import generic_helper

app = FastAPI()

inprogress_order = {}

@app.post("/")
async def handle_request(request: Request):
    payload = await request.json()
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']

    session_id = generic_helper.extract_session_id(output_contexts[0]['name'])
    session_order_number = output_contexts[0]['parameters']['number']

    intent_handler_dict = {
        'order.add - context: ongoing-order': add_to_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order - context: ongoing-tracking': track_order
    }
    
    if intent == 'track.order - context: ongoing-tracking':
        return intent_handler_dict[intent](parameters, session_id, session_order_number)
    else:
        return intent_handler_dict[intent](parameters, session_id)

def add_to_order(parameters: dict, session_id:str):
    food_items = parameters['food-items']
    quantities = parameters['number']

    if len(food_items) != len(quantities):
        fulfillment_text = "Please provide the same number of food items and quantities"
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_order:
            inprogress_order[session_id].update(new_food_dict)
        else:
            inprogress_order[session_id] = new_food_dict
        order_str = generic_helper.get_str(inprogress_order[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })

def remove_from_order(parameters:dict , session_id: str):
    if session_id not in inprogress_order:
        return JSONResponse(content={
        "fulfillmentText" : "You have not placed any order yet. Please add some items to your order"
    })
        
    current_order = inprogress_order[session_id]
    food_items = parameters['food-items']
    removed_items = []
    no_such_items = []
    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]
    
    if len(removed_items) >0:
        fulfillment_text = f"Removed {",".join(removed_items)} from your order. "
    if len(no_such_items) > 0:
        fulfillment_text = f"Your order does not contain {",".join(no_such_items)} "
    
    if len(current_order.keys()) == 0:
        fulfillment_text += "Your order is empty"
    else:
        order_str = generic_helper.get_str(current_order)
        fulfillment_text += f"Here is what left in your order: {order_str}. Do you need anything else?"


    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })

def complete_order(parameters:dict , session_id: str):
    if session_id not in inprogress_order:
        fulfillment_text = "You have not placed any order yet. Please add some items to your order"
    else:
        order = inprogress_order[session_id]
        order_id = save_to_db(order)

        if order_id == -1:
            fulfillment_text = "Sorry, we are unable to process your order at this time. Please try again later"
        else:
            order_total = db_helper.get_total_order_price(order_id)
            fulfillment_text = f"Your order has been placed. Your order id is {order_id}." \
                               f"Your order total is {order_total} which u can pay at time of delivery"
    
    del inprogress_order[session_id]

    return JSONResponse(content={
        "fulfillmentText" : fulfillment_text
    })



def save_to_db(order:dict):
    next_order_id = db_helper.get_next_order_id()

    for food,quantity in order.items():
        rcode = db_helper.insert_order_item(
            food,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1
    
    db_helper.insert_order_tracking(next_order_id, "in progress")

    return next_order_id

def track_order(parameters: dict, session_id:str,session_order_number):
    order_id = int(parameters['number'])
    order_status = db_helper.get_order_status(order_id)

    if order_status:
        fulfillment_text = f"The order status for order id {order_id} is {order_status}"
    else:
        fulfillment_text = f"No order found with order id: {order_id}"


    return JSONResponse(content={
            'fulfillmentText' : fulfillment_text
        })

    # order_status = db_helper.get_order_status(session_order_number)

    # if session_order_number:
    #     fulfillment_text = f"The order status for order id {session_order_number} is {order_status}"
    # else:
    #     fulfillment_text = f"No order found for the User"


    # return JSONResponse(content={
    #         'fulfillmentText' : fulfillment_text
    #     })
