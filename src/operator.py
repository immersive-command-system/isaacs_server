from drone import Drone
from sensor import Sensor
import roslibpy
#from topic_types import topic_types
#from drone_msg import drone_msg
#from sensor_msg import sensor_msg
#roslaunch rosbridge_server rosbridge_websocket.launch

#####################
# Global Parameters #
#####################
HOST = '136.25.185.6'

####################
# Global Variables #
####################

drones = dict() # Global map between drone IDs and drone instances
sensors = dict() # Global map between sensor IDs and sensor instances
drone_names = dict() # Global map between drone names and drone IDs
sensor_names = dict() # Global map between sensor names and sensor IDs
all_topics = dict() # Global map of topic names to topic types
# If an id of 0 is passed in, it refers to all drones, sensors, and global topics
next_id = 1 # ID to assign next drone or sensor

###################################
# Set up and boot Roslibpy server #
###################################

ROS_master_connection = roslibpy.Ros(host=HOST, port=9090)
services = []
# Use the @custom_service decorator on a handler method to have it automatically advertise as a Service.
def custom_service(handler):
    exceptions = {
        'save_drone_topics': 'isaacs_server/type_to_topic',
        'save_sensor_topics': 'isaacs_server/type_to_topic',
        'shutdown_drone': 'isaacs_server/type_to_topic',
        'shutdown_sensor': 'isaacs_server/type_to_topic'
    }
    if handler.__name__ in exceptions:
        serv_type = exceptions[handler.__name__]
    else:
        serv_type = f'isaacs_server/{handler.__name__}'
    service = roslibpy.Service(ROS_master_connection, f'/isaacs_server/{handler.__name__}', serv_type)
    print(service.name)
    service.advertise(handler)
    services.append(service)
    return handler

################################
# Interface -> Server Handlers #
################################

# Todo Implement
@custom_service
def all_drones_available(request, response):

    #dont have list of services
    #drones_available = {k: {drone_name: v.name, drone_subs: v.topics} for k, v in drones}

    drones_available = []
    print("Calling all_drones_available_service ...")
    for k, v in drones.items():
        avail = dict()
        avail["id"] = k
        avail["name"] = v.drone_name
        avail["type"] = v.drone_type
        avail["topics"] = v.topics
        #TODO fix services
        avail["services"] = v.services
        drones_available.append(avail)

    response["success"] = True
    response["message"] = "Successfully sent all available drones to VR"
    #response['drones_available'] = []
    response['drones_available'] = drones_available
    print("All_drones_available_service finished")

    return True

@custom_service
def upload_mission(request, response):
    '''
    :param request: dict of {drone_id: int, waypoints: list of ints/strings --> pass
    these directly into the drone instance}
    '''
    if not drones[request["drone_id"]]:
        response["success"] = False
        response["message"] = "No drone with that id."
        response["drone_id"] = -1
        return False
    response = drones[request["drone_id"]].upload_mission(request["waypoints"])
    return True

# Todo Implement
@custom_service
def set_speed(request, response):
    print('Setting speed to {}'.format(request['data']))
    response['success'] = True
    return True

# Todo Implement
# includes startmission, pausemission, resume mission, landdrone, flyhome
@custom_service
def control_drone(request, response):
    control_task = request["control_task"]
    drone = drones.get(request["drone_id"])
    if control_task == "start_mission":
        response = drone.start_mission()
    elif control_task == "pause_mission":
        response = drone.pause_mission()
    elif control_task == "resume_mission":
        response = drone.resume_mission()
    elif control_task == "land_drone":
        response = drone.land_drone()
    elif control_task == "fly_home":
        response = drone.fly_home()
    else:
        response["success"] = False
        response["message"] = "Invalid control task"
    return True

@custom_service
def query_topics(request, response):
    id = request["id"]
    response["id"] = id
    all_topics_response = []
    if id == 0:
        for k,v in all_topics.items():
            all_topics_response.append({"name": k, "type": v})
    else:
        if not drones[id] and not sensors[id]:
            response["success"] = False
            response["message"] = "No drone or sensor with that id."
            return False
        if id in drones:
            all_topics_response = drones[id].topics
            for sensor_id in drones[id].sensors:
                all_topics_response += sensors[sensor_id].topics
        else:
            all_topics_response = sensors[id].topics

    response["all_topics"] = all_topics_response
    response["success"] = True
    response["message"] = "Successfully queried topics."
    return True


''' Funtions to implement
Click button - query drone ID from button
SelectedDrone.waypoints -
Example: MatriceRosDroneConnection
UploadMissionCallback()
StartMission(ID)
StartMissionCallback()
PauseMission(ID)
PauseMissionCallback()
ResumeMission(ID)
ResumeMissionCallback()
LandDrone(ID)
LandDroneCallback()
FlyHome(ID)
FlyHomeCallback()
'''


############################
# Drone -> Server Handlers #
############################

@custom_service
def register_drone(request, response):
    '''
    :param request: dict of {drone_name: string, drone_type: string}
    '''

    def get_id():
        global next_id
        cur_id, next_id = next_id, next_id + 1
        return cur_id

    drone_name = request["drone_name"]
    drone_type = request["drone_type"]
    print(f"\tDroneType: {request['drone_type']}\n")

    # Create new drone instance using base class constructor, which should then
    # call child constructor corresponding to the drone_type
    d=Drone.create(drone_name, drone_type)
    successful=False

    if d:
        id = get_id()
        d.id=id
        drones[id] = d
        drone_names[drone_name] = id
        successful = True
        response["success"] = successful
        response["drone_id"] = id
    print(f"Adding drone {id} to global drones map with following properties:")

    #TODO fix message to error
    if successful:
        response["message"] = "Drone registered"
    else:
        response["message"] = "Failed to register drone"

    print(drones)
    print(drone_names)

    return True # TODO check where this return goes to

@custom_service
def save_drone_topics(request, response):
    publishes = request["publishes"]
    id = request["id"]

    if drones[id] == None:
        response["success"] = False
        response["message"] = "Drone id does not exist"
        return False

    for topic in publishes:
        all_topics[topic["name"]] = topic["type"]
        drones[id].topics.append(topic)

    response["success"] = True
    response["message"] = "Successfully saved drone topics"
    print(all_topics)
    return True


@custom_service
def shutdown_drone(request, response):
    '''
    :param request: message that has a drone_id: std_msgs/Int32 and drone_subs: issacs_server/topic[]
    '''
    id = request["id"]
    publishes = request["publishes"]
    successful = False
    if id in drones:

        drone_names.pop(drones[id].drone_name)
        drones.pop(id)
        for topic in publishes:
            all_topics.pop(topic['name'])

        # TODO ensure that drone instance is completely terminated
        # TODO Remove drone_subs from global topics dict

        successful = True
    response["success"] = successful
    if successful:
        response["message"] = "Drone successfully shutdown"
    else:
        response["message"] = "Failed to shutdown drone"

    print(drone_names)
    print(drones)
    print(all_topics)
    return True


############################
# Sensor -> Server Handlers #
############################
@custom_service
def register_sensor(request, response):
    '''
    :param request: dict of {drone_name: string, drone_type: string}
    '''

    #TODO error checking fixes ID when bad Sensor init
    def get_id():
        global next_id  #TODO FIXME
        cur_id, next_id = next_id, next_id + 1
        return cur_id

    sensor_name = request["sensor_name"]
    sensor_type = request["sensor_type"]
    parent_drone_name = request["parent_drone_name"]
    print(f"\tSensorType: {request['sensor_type']}\n")

    s=Sensor.create(drone_name, drone_type, drone_names[parent_drone_name])
    successful=False

    if s:
        id = get_id()
        s.id=id
        sensors[id] = s
        sensor_names[sensor_name] = id
        successful = True
        response["success"] = successful
        response["sensor_id"] = id

    # TODO Instantiate Sensor Object
    print(f"Adding sensor {id} to global sensor map with following properties:")

    #TODO fix message to error
    if successful:
        response["message"] = "Registering sensor"
    else:
        response["message"] = "Failed to register sensor"

    return True # TODO check where this return goes to
@custom_service
def save_sensor_topics(request, response):
    publishes = request["publishes"]
    id = request["id"]

    if sensors[id] == None:
        response["success"] = False
        response["message"] = "Sensor id does not exist"
        return False

    for topic in publishes:
        all_topics[topic["name"]] = topic["type"]
        sensors[id].topics.append(topic)

    response["success"] = True
    response["message"] = "Successfully saved sensor topics"

    return True

@custom_service
def shutdown_sensor(request, response):
    '''
    :param request: message that has a sensor_id: std_msgs/Int32 and sensor_subs: issacs_server/topic[]
    '''
    sensor_id = request["id"]
    publishes = request["publishes"]
    successful = False
    if sensor_id in sensors:
        # TODO Fix when sensor class is done
        sensor_names.pop(sensors[id].sensor_name)
        sensors.pop(sensor_id)
        for topic in publishes:
            all_topics.pop(topic['name'])
        # TODO ensure that sensor instance is completely terminated
        # TODO Remove sensor_subs from global topics dict
        successful = True
    response["success"] = successful
    if successful:
        response["message"] = "Sensor successfully shutdown"
    else:
        response["message"] = "Failed to shutdown sensor"

    return True


###################################
# Set up and boot Roslibpy server #
###################################
# Uncomment service advertises as needed
# register_drone_service = roslibpy.Service(ROS_master_connection, '/register_drone', 'isaacs_server/register_drone')
# register_drone_service.advertise(register_drone)
#
# save_drone_topics_service = roslibpy.Service(ROS_master_connection, '/save_drone_topics', 'isaacs_server/type_to_topic')
# save_drone_topics_service.advertise(save_drone_topics)
#
# shutdown_drone_service = roslibpy.Service(ROS_master_connection, '/shutdown_drone', 'isaacs_server/type_to_topic')
# shutdown_drone_service.advertise(shutdown_drone)
#
#
# register_sensor_service = roslibpy.Service(ROS_master_connection, '/register_sensor', 'isaacs_server/register_sensor')
# register_sensor_service.advertise(register_sensor)
#
# save_sensor_topics_service = roslibpy.Service(ROS_master_connection, '/save_sensor_topics', 'isaacs_server/type_to_topic')
# save_sensor_topics_service.advertise(save_sensor_topics)
#
# shutdown_sensor_service = roslibpy.Service(ROS_master_connection, '/shutdown_sensor', 'isaacs_server/type_to_topic')
# shutdown_sensor_service.advertise(shutdown_sensor)
#
#
#
# all_drones_available_service = roslibpy.Service(ROS_master_connection, '/all_drones_available', 'isaacs_server/all_drones_available')
# all_drones_available_service.advertise(all_drones_available)
#
# upload_mission_service = roslibpy.Service(ROS_master_connection, '/upload_mission', 'isaacs_server/upload_mission')
# upload_mission_service.advertise(upload_mission)
#
#
# set_speed_service = roslibpy.Service(ROS_master_connection, '/set_speed', 'isaacs_server/set_speed')
# set_speed_service.advertise(set_speed)'''
#
# control_drone_service = roslibpy.Service(ROS_master_connection, '/control_drone', 'isaacs_server/control_drone')
# control_drone_service.advertise(control_drone)

print('Services advertised.')

ROS_master_connection.run_forever()
ROS_master_connection.terminate()
