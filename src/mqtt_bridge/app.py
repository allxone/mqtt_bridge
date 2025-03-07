# -*- coding: utf-8 -*-
from __future__ import absolute_import

import inject
import paho.mqtt.client as mqtt
import rospy

from .bridge import create_bridge
from .mqtt_client import create_private_path_extractor
from .util import lookup_object


def create_config(mqtt_client, serializer, deserializer, private_path_extractor):
    if isinstance(serializer, basestring):
        serializer = lookup_object(serializer)
    if isinstance(deserializer, basestring):
        deserializer = lookup_object(deserializer)
    def config(binder):
        binder.bind('serializer', serializer)
        binder.bind('deserializer', deserializer)
        binder.bind(mqtt.Client, mqtt_client)
        binder.bind('mqtt_private_path_extractor', private_path_extractor)
    return config


def mqtt_bridge_node():
    # init node
    rospy.init_node('mqtt_bridge_node')

    # load parameters
    params = rospy.get_param("~", {})
    mqtt_params = params.pop("mqtt", {})
    conn_params = mqtt_params.pop("connection")
    mqtt_private_path = mqtt_params.pop("private_path", "")
    bridge_params = params.get("bridge", [])

    private_path_extractor = create_private_path_extractor(mqtt_private_path)

    # create mqtt client
    mqtt_client_factory_name = rospy.get_param(
        "~mqtt_client_factory", ".mqtt_client:default_mqtt_client_factory")
    mqtt_client_factory = lookup_object(mqtt_client_factory_name)
    mqtt_client = mqtt_client_factory(mqtt_params, private_path_extractor)

    # load serializer and deserializer
    serializer = params.get('serializer', 'json:dumps')
    deserializer = params.get('deserializer', 'json:loads')

    # dependency injection
    config = create_config(
        mqtt_client, serializer, deserializer, private_path_extractor)
    inject.configure(config)

    # configure and connect to MQTT broker
    bridges = []
    mqtt_client.on_connect = _on_connect_wrapper(bridges, bridge_params)
    mqtt_client.on_disconnect = _on_disconnect
    mqtt_client.connect(**conn_params)

    # configure bridges

    # start MQTT loop
    mqtt_client.loop_start()

    # register shutdown callback and spin
    if mqtt_params.get('disconnect_on_shutdown', True):
        rospy.on_shutdown(mqtt_client.disconnect)
    rospy.on_shutdown(mqtt_client.loop_stop)
    rospy.spin()

def _on_connect_wrapper(bridges, bridge_params):
    def _on_connect(client, userdata, flags, response_code):
        rospy.loginfo('MQTT connected')
        del bridges[:]
        for bridge_args in bridge_params:
            bridges.append(create_bridge(**bridge_args))
    return _on_connect


def _on_disconnect(client, userdata, response_code):
    rospy.loginfo('MQTT disconnected')


__all__ = ['mqtt_bridge_node']
