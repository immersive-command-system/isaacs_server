from drone import Drone
from sensor import Sensor
import roslibpy
import roslibpy.actionlib
import argparse
import constants
#roslaunch rosbridge_server rosbridge_websocket.launch

#####################
# Global Parameters #
#####################
# Allows option to specify --ip of the server through the command line.
# Ex: python3 operator.py --ip 0.0.0.0
parser = argparse.ArgumentParser(
        description='Starts the operator of the server.')
parser.add_argument('--ip', type=str, default=constants.IP_ADDRESS)
args = parser.parse_args()

# HOST ip parameter
HOST = args.ip

####################
# Global Variables #
####################

drones = dict() # Global map between drone IDs and drone instances
sensors = dict() # Global map between sensor IDs and sensor instances
drone_names = dict() # Global map between drone names and drone IDs
sensor_names = dict() # Global map between sensor names and sensor IDs
all_topics = dict() # Global map of topic names to topic types
# If an id of 0 is passed in, it acts as a wild card.
next_id = 1 # ID to assign next drone or sensor
services = [] # TODO list of all services
actions = [] # TODO list of all actions
latestService = [] # Remembers last service call
#first element is request, second element is response, third element is servicename

###################################
# Set up and boot Roslibpy server #
###################################

ROS_master_connection = roslibpy.Ros(host=HOST, port=9090)

def to_camel_case(snake_str):
    components = snake_str.split('_')
    # We capitalize the first letter of each component
    # with the 'title' method and join them together.
    return ''.join(x.title() for x in components)

# Use the @custom_service decorator on a handler method to have it
# automatically advertise as a Service.
def custom_service(handler):
    """
    This method is designed to be used as a decorator (@custom_service)
    to advertise the handler method as a service via the ROS_master_connection.
    By default, the service can be found at `/isaacs_server/[handler_name]`
    with a service type of `isaacs_server/[handler_name]`.

    Exceptions for the handler name to service type mapping can be added
    to the exceptions dictionary.

    parameter: handler(request, response) handles an incoming service request.
    returns: handler
    """
    exceptions = {
        'save_drone_topics': 'isaacs_server/TypeToTopic',
        'save_sensor_topics': 'isaacs_server/TypeToTopic',
        'shutdown_drone': 'isaacs_server/TypeToTopic',
        'shutdown_sensor': 'isaacs_server/TypeToTopic'
    }
    if handler.__name__ in exceptions:
        serv_type = exceptions[handler.__name__]
    else:
        serv_type = f'isaacs_server/{to_camel_case(handler.__name__)}'
    service = roslibpy.Service(ROS_master_connection,
            f'/isaacs_server/{handler.__name__}', serv_type)
    print(service.name)
    service.advertise(handler)
    services.append(service)
    return handler

# Use the @custom_action decorator on a handler method to have it
# automatically advertise as an Action.
def custom_action(handler):
    """
    This method is designed to be used as a decorator (@custom_action)
    to advertise the handler method as a service via the ROS_master_connection.
    By default, the service can be found at `/isaacs_server/[handler_name]/Action`
    with a service type of `isaacs_server/[handler_name]Action`.

    Exceptions for the handler name to service type mapping can be added
    to the exceptions dictionary.

    parameter: handler(request, response) handles an incoming action request.
    returns: handler
    """
    exceptions = {}
    if handler.__name__ in exceptions:
        action_type = exceptions[handler.__name__]
    else:
        action_type = f'isaacs_server/{to_camel_case(handler.__name__)}Action'
    
    print(action_type)
    server = roslibpy.actionlib.SimpleActionServer(ROS_master_connection,
            f'isaacs_server/{handler.__name__}', action_type)
    handler = handler(server)
    server.start(handler)
    actions.append(server)
    return handler

def get_id(client_type):
    '''
    Assigns an new ID to the client type inputted.

    :param client_type: Expects the type of client that an id is assigned to
    (either a Sensor or a Drone)
    This function assigns an id to a Drone or a Sensor.
    The protocol for id assignment is that Drones are odd numbered and
    Sensors are even numbered. (This way it is known what an id corresponds to)
    '''
    global next_id
    if client_type == Drone:
        if next_id % 2 == 1:
            cur_id, next_id = next_id, next_id + 1
        else:
            cur_id, next_id = next_id + 1, next_id + 2
    else:
        if next_id % 2 == 0:
            cur_id, next_id = next_id, next_id + 1
        else:
            cur_id, next_id = next_id + 1, next_id + 2
    return cur_id

def is_drone(client_id):
    '''
    Verifies that the client_id is a drone ID or not.

    :param client_id: id of client to identify
    '''
    if client_id % 2 == 1:
        return True
    return False

def is_sensor(client_id):
    '''
    Verifies that the client_id is a sensor ID or not.

    :param client_id: id of client to identify
    '''
    if client_id % 2 == 0:
        return True
    return False

def checkLatestService(request, serviceName):
    if len(latestService) == 3 and serviceName == latestService[2] and request == latestService[0]:
        print("Repeat service call")
        print(latestService[1])
        print(latestService[1]["success"])
        return True
    return False

def saveLatestService(request, response, serviceName):
    global latestService
    latestService = [request, response, serviceName]

################################
# Interface -> Server Handlers #
################################
@custom_service
def all_drones_available(request, response):

    print("Calling all_drones_available service...")
    if checkLatestService(request, "all_drones_available"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        response["drones_available"] = latestService[1]["drones_available"]
        return True

    drones_available = []
    for k, v in drones.items():
        avail = {
                "id" : k,
                "name" : v.drone_name,
                "type" : v.drone_type,
                "topics" : v.topics,
                "services" : v.services
        }
        drones_available.append(avail)

    response["success"] = True
    response["message"] = "Successfully sent all available drones to VR"
    response['drones_available'] = drones_available
    print("All_drones_available service finished!", response)

    saveLatestService(request, response, "all_drones_available")
    return True

@custom_service
def query_topics(request, response):
    print("Calling query_topics service...")
    if checkLatestService(request, "query_topics"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        response["id"] = latestService[1]["id"]
        return True

    client_id = request["id"]
    response["id"] = client_id
    all_topics_response = []
    if client_id == 0:
        for k,v in all_topics.items():
            all_topics_response.append({"name": k, "type": v})
    else:
        if client_id in drones:
            all_topics_response = drones[client_id].topics
            for sensor_id in drones[client_id].sensors:
                all_topics_response += sensors[sensor_id].topics
        elif client_id in sensors:
            all_topics_response = sensors[client_id].topics
        else:
            response["success"] = False
            response["message"] = "No drone or sensor with that id."
            saveLatestService(request, response, "query_topics")
            return True

    response["all_topics"] = all_topics_response
    response["success"] = True
    response["message"] = "Successfully queried topics."
    print(all_topics_response)
    print("Query_topics service finished!")
    print(response)
    saveLatestService(request, response, "query_topics")
    return True

############################
# Drone -> Server Handlers #
############################
@custom_service
def register_drone(request, response):
    '''
    :param request: dict of {drone_name: string, drone_type: string}
    '''
    print("Calling register_drone service...")
    if checkLatestService(request, "register_drone"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        response["id"] = latestService[1]["id"]
        return True

    drone_name = request["drone_name"]
    drone_type = request["drone_type"]

    if drone_name in drone_names:
        response["success"] = False
        response["message"] = "A drone with this name already exists."
        response["id"] = 0
        print("A drone with the name", drone_name, "already exists")
        saveLatestService(request, response, "register_drone")
        return True

    # Create new drone instance using base class constructor, which should then
    # call child constructor corresponding to the drone_type
    d=Drone.create(drone_name, drone_type, ROS_master_connection)
    if d:
        drone_id = get_id(Drone)
        print(f"Adding drone {id} to global drones map...")
        d.id = drone_id
        d.drone_namespace = '/drone_' + str(drone_id)
        drones[drone_id] = d
        drone_names[drone_name] = drone_id
        response["success"] = True
        response["id"] = drone_id
        response["message"] = "Drone registered"
    else:
        response["success"] = False
        response["message"] = "Failed to register drone"
        response["id"] = -1
    print(drones)
    print(drone_names)
    print("Register_drone service finished!")
    saveLatestService(request, response, "register_drone")
    return True


@custom_service
def save_drone_topics(request, response):
    """
    Adds topics to the given drone.

    :param request: message that has a drone id: std_msgs/Int32
        and publishes: issacs_server/topic[]
    This service saves all topics provided into the appropriate drone object.
    """
    print("Calling save_drone_topics...")
    if checkLatestService(request, "save_drone_topics"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        return True

    publishes = request["publishes"]
    drone_id = request["id"]
    if not drone_id in drones:
        response["success"] = False
        response["message"] = "Drone id does not exist"
        return True
    for topic in publishes:
        all_topics[topic["name"]] = topic["type"]
        drones[drone_id].topics.append(topic)
    response["success"] = True
    response["message"] = "Successfully saved drone topics"
    print(all_topics)
    print("Save_drone_topics service finished!")
    saveLatestService(request, response, "save_drone_topics")
    return True


@custom_service
def shutdown_drone(request, response):
    '''
    Shuts down the drone. Please ensure that the drone is landed.

    :param request: message that has a id: std_msgs/Int32
        and publishes: issacs_server/topic[]
    '''
    print("Calling shutdown_drone service...")
    if checkLatestService(request, "shutdown_drone"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        return True

    drone_id = request["id"]
    publishes = request["publishes"]
    d = drones.pop(drone_id, None)
    if d:
        drone_names.pop(d.drone_name)
        for topic in publishes:
            all_topics.pop(topic['name'])
        d.shutdown()
        response["success"] = True
        response["message"] = "Drone shutdown"
    else:
        response["success"] = False
        response["message"] = "failed to shutdown drone"
        print("Failed to shutdown drone. ID", drone_id, "not found")
        saveLatestService(request, response, "shutdown_drone")
        return True

    print(drone_names)
    print(drones)
    print("Shutdown_drone service finished!")
    saveLatestService(request, response, "shutdown_drone")
    return True


############################
# Sensor -> Server Handlers #
############################
@custom_service
def register_sensor(request, response):
    '''
    :param request: dict of {drone_name: string, drone_type: string}
    Parent drone must be initiated before sensors are registered.
    '''
    print("Calling register_sensor service...")
    if checkLatestService(request, "register_sensor"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        response["id"] = latestService[1]["id"]
        return True

    sensor_name = request["sensor_name"]
    sensor_type = request["sensor_type"]
    parent_drone_name = request["parent_drone_name"]

    if sensor_name in sensor_names:
        response["success"] = False
        response["message"] = "A sensor with this name already exists."
        response["id"] = 0
        print("A sensor with the name", sensor_name, "already exists")
        saveLatestService(request, response, "register_sensor")
        return True

    s = None
    if parent_drone_name in drone_names:
        parent_drone_id = drone_names[parent_drone_name]
        sensor_id = get_id(Sensor)
        s = Sensor.create(sensor_name, sensor_type, ROS_master_connection, parent_drone_id, sensor_id)
        print(f"Adding sensor {id} to global sensor map.")
        sensors[sensor_id] = s
        sensor_names[sensor_name] = sensor_id
        drones.get(parent_drone_id).sensors.append(s)
        response["success"] = True
        response["id"] = s.id
        response["message"] = "Sensor registered"
    else:
        response["success"] = False
        response["id"] = 0
        response["message"] = "No drone with that name."

    print(sensor_names)
    print(sensors)
    print("Register_sensor service finished!")
    saveLatestService(request, response, "register_sensor")
    return True


@custom_service
def save_sensor_topics(request, response):
    '''
    :param request: message that has a sensor id: std_msgs/Int32
        and publishes: issacs_server/topic[]
    This adds all of the sensor topics provided into the sensor object.
    This service is called by the sensor client.
    '''
    print("Calling save_sensor_topics service...")
    if checkLatestService(request, "save_sensor_topics"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        return True

    publishes = request["publishes"]
    sensor_id = request["id"]
    sensor = sensors.get(sensor_id)
    if not sensor:
        response["success"] = False
        response["message"] = "Sensor id does not exist"
        saveLatestService(request, response, "save_sensor_topics")
        return True
    for topic in publishes:
        all_topics[topic["name"]] = topic["type"]
        sensor.topics.append(topic)
    response["success"] = True
    response["message"] = "Successfully saved sensor topics"
    print(all_topics)
    print("Save_sensor_topics service finished!")
    saveLatestService(request, response, "save_sensor_topics")
    return True


@custom_service
def shutdown_sensor(request, response):
    '''
    :param request: message that has a id: std_msgs/Int32
        and publishes: issacs_server/topic[]
    '''
    print("Calling shutdown_sensor service...")
    if checkLatestService(request, "shutdown_sensor"):
        response["message"] = latestService[1]["message"]
        response["success"] = latestService[1]["success"]
        return True

    sensor_id = request["id"]
    publishes = request["publishes"]
    s = sensors.pop(sensor_id, None)
    if s:
        sensor_names.pop(s.sensor_name)
        for topic in publishes:
            all_topics.pop(topic['name'])
        drones.get(s.parent_drone_id).sensors.remove(s)
        s.shutdown()
        response["success"] = True
        response["message"] = "Sensor successfully shutdown"
    else:
        response["success"] = False
        response["message"] = "Failed to shutdown sensor"

    print(sensor_names)
    print(sensors)
    print("Shutdown_sensor service finished!")
    saveLatestService(request, response, "shutdown_sensor")
    return True

@custom_service
def reset(request, response):
    print("Resetting server")
    global drones
    global sensor
    global drone_names
    global sensor_names
    global all_topics
    global next_id
    global services
    global latestService
    drones = dict() # Global map between drone IDs and drone instances
    sensors = dict() # Global map between sensor IDs and sensor instances
    drone_names = dict() # Global map between drone names and drone IDs
    sensor_names = dict() # Global map between sensor names and sensor IDs
    all_topics = dict() # Global map of topic names to topic types
    # If an id of 0 is passed in, it acts as a wild card.
    next_id = 1 # ID to assign next drone or sensor
    services = [] # TODO list of all services
    latestService = [] # Remembers last service call
    response["success"] = True
    response["message"] = "Server successfully reset."
    print("Server Reset")
    return True


print('Services advertised.')

@custom_action
def control_drone(server):
    def control_drone(goal):
        print("Calling control_drone action...")
        server.send_feedback({"progress": "Calling control_drone action..."})

        control_task = goal["control_task"]
        drone = drones.get(goal["id"])
        if not drone:
            print(f"could not find drone with id {goal['id']}")
            server.set_succeeded({"id":goal["id"], "success":False, "message":"No drone with that id."})
        else:
            tasks = {
                "start_mission" : drone.start_mission,
                "pause_mission" : drone.pause_mission,
                "resume_mission" : drone.resume_mission,
                "stop_mission" : drone.stop_mission,
                "land_drone" : drone.land_drone,
                "fly_home" : drone.fly_home
            }
            print(f"Executing {control_task}...")
            callback = tasks.get(control_task)()
            print("Control_drone service finished!")
            server.send_feedback({"progress": "Control_drone action finished!"})
            server.set_succeeded({"id":drone.id, "control_task": control_task, "success":callback["success"], "message":callback["message"]})
    return control_drone

@custom_action
def upload_mission(server):
    def upload_mission(goal):
        print("Calling upload_mission action...")
        server.send_feedback({"progress": "Calling upload_mission action..."})

        d = drones.get(goal["id"])
        if not d:
            print(f"could not find drone with id {goal['id']}")
            server.set_succeeded({"id":goal["id"], "success":False, "message":"No drone with that id."})
        else:
            print("id: ", goal["id"], "waypoints: ", goal["waypoints"])
            callback = d.upload_mission(goal["waypoints"])
            print("Upload_mission action finished!")
            server.send_feedback({"progress": "Upload_mission action finished!"})
            server.set_succeeded({"id":d.id, "success":callback["success"], "message":callback["message"]})
    return upload_mission

@custom_action
def set_speed(server):
    def set_speed(goal):
        print("Calling set_speed action...")

        d = drones.get(goal["id"])
        if not d:
            print(f"could not find drone with id {goal['id']}")
            server.set_succeeded({"id":goal["id"], "success":False, "message":"No drone with that id."})
        else:
            print('Setting speed to {}...'.format(goal['speed']))
            callback = d.set_speed(goal["speed"])
            print("Set_speed service finished!")
            server.send_feedback({"progress": "Set_speed service finished!"})
            server.set_succeeded({"id":d.id, "success":callback["success"], "message":callback["message"]})
    return set_speed

@custom_action
def get_speed(server):
    def get_speed(goal):
        print("Calling get_speed service...")

        d = drones.get(goal["id"])
        if not d:
            print(f"could not find drone with id {goal['id']}")
            server.set_succeeded({"id":goal["id"], "success":False, "message":"No drone with that id.", "speed":0})
        else:
            print('Getting speed')
            callback = d.get_speed()
            print("Get_speed service finished!")
            server.send_feedback({"progress": "Get_speed service finished!"})
            server.set_succeeded({"id":d.id, "success":callback["success"], "message":callback["message"], "speed":callback["speed"]})
    return get_speed

print("Starting actions...")

ROS_master_connection.run_forever()
ROS_master_connection.terminate()
