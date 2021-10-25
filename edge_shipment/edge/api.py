import json

import requests
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from edge_shipment.settings import settings
from . import models
from .models import Sensory, Order, Message, Status


# Serializer
class SensoryListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        sensory_data_list = [Sensory(**item) for item in validated_data]
        return Sensory.objects.bulk_create(sensory_data_list)


class SensorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensory
        fields = '__all__'
        list_serializer_class = SensoryListSerializer


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


def find_target_order(item_type):
    orders = Order.objects.filter(item_type=item_type)

    if len(orders) == 0:
        return None
    else:
        return orders[0]


# Sensory Data
class SensoryViewSet(viewsets.ModelViewSet):
    queryset = Sensory.objects.all()
    serializer_class = SensorySerializer
    http_method_names = ['post']

    @swagger_auto_schema(responses={400: "Bad Request"})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, headers=headers)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    http_method_names = ['post']

    @swagger_auto_schema(
        responses={400: "Bad request", 204: "Invalid Message Title / Invalid Message Sender / Not allowed"})
    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        sender = int(request.data['sender'])
        title = request.data['title']

        if sender == models.MACHINE_SHIPMENT:
            if title == 'Running Check':
                if len(Status.objects.all()) == 0:
                    return Response("Not allowed", status=204)

                current_status = Status.objects.all()[0]

                if current_status.status:
                    return Response(status=201)

                return Response("Not allowed", status=204)

            if title == 'Sending Check':
                item_type = int(request.data['msg'])
                target_order = find_target_order(item_type)

                if target_order is not None:
                    dest = target_order.dest
                    target_order.delete()

                    process_message = {'sender': models.EDGE_SHIPMENT,
                                       'title': 'Order Processed',
                                       'msg': json.dumps({'item_type': item_type, 'dest': dest})}
                    requests.post(settings['edge_repository_address'] + '/api/message/', data=process_message)
                    requests.post(settings['cloud_address'] + '/api/message/', data=process_message)

                    return Response(dest, status=201)

                return Response("Not allowed", status=204)

            return Response("Invalid Message Title", status=204)

        if sender == models.CLOUD:
            if title == 'Order Created':
                order_data = json.loads(request.data['msg'])
                new_order = Order(item_type=int(order_data['item_type']), made=order_data['made'],
                                  dest=order_data['dest'])
                new_order.save()

                return Response(status=201)

            if title == 'Start':
                Order.objects.all().delete()

                if len(Status.objects.all()) == 0:
                    current_state = Status()
                else:
                    current_state = Status.objects.all()[0]

                current_state.status = True
                current_state.save()
                return Response(status=201)

            if title == 'Stop':
                if len(Status.objects.all()) == 0:
                    current_state = Status()
                else:
                    current_state = Status.objects.all()[0]

                current_state.status = False
                current_state.save()
                return Response(status=201)

            return Response("Invalid Message Title", status=204)

        return Response("Invalid Message Sender", status=204)
