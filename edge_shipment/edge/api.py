import requests
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from edge_shipment.settings import settings
from . import models
from .models import Sensory, Order, Message


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

    @swagger_auto_schema(responses={400: "Bad request / Invalid Message Title / Invalid Message Sender / Not allowed"})
    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        sender = request.data['sender']
        title = request.data['title']

        if sender == models.MACHINE_REPOSITORY_1 or sender == models.MACHINE_REPOSITORY_2 or sender == models.MACHINE_REPOSITORY_3:
            if title == 'Sending Check':
                item_type = request.data['msg']['item_type']
                target_order = Order.objects.filter(item_type=item_type)[0]

                if target_order is not None:
                    dest = target_order.dest
                    target_order.delete()

                    process_message = {'sender': models.EDGE_SHIPMENT,
                                       'title': 'Order Processed',
                                       'msg': {'item_type': item_type, 'dest': dest}}
                    requests.post(settings['edge_repository_address'] + '/api/message/', data=process_message)
                    requests.post(settings['cloud_address'] + '/api/message/', data=process_message)

                    return Response({201: dest})

                return Response({400: "Not allowed"})

            return Response({400: "Invalid Message Title"})

        if sender == models.CLOUD:
            if title == 'Order Created':
                msg = request.data['msg']
                new_order = Order(item_type=int(msg['item_type']), made=msg['made'], dest=msg['dest'])
                new_order.save()

                return Response(201)

            return Response({400: "Invalid Message Title"})

        return Response({400: "Invalid Message Sender"})
