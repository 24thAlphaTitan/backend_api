from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Company , RazorpayPayment
import json
import random
import string
from uuid import uuid4
import subprocess
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image
import base64
from io import BytesIO
import tempfile
import os
import razorpay
from rest_framework.views import APIView
from  .VTON_MODEL.gradio_demo.app import start_tryon
import cv2

RAZOR_KEY_ID = os.getenv('RAZORPAY_KEY_ID', None)
RAZOR_KEY_SECRET = os.getenv('RAZORPAY_SECRET_KEY', None)

# Creating Razorpay Client instance.
razorpay_client = razorpay.Client(auth=(RAZOR_KEY_ID, RAZOR_KEY_SECRET))

class RazorpayPaymentView(APIView):
    """
    APIView for Creating Razorpay Order.
    :return: list of all necessary values to open Razopary SDK
    """

    http_method_names = ('post',)

    @staticmethod
    def post(request, *args, **kwargs):

        # Take Order Id from frontend and get all order info from Database.
        # order_id = request.data.get('order_id', None)

        # Here We are Using Static Order Details for Demo.
        name = "Swapnil Pawar"
        amount = 400

        # Create Order
        razorpay_order = razorpay_client.order.create(
            {"amount": int(amount) * 100, "currency": "INR", "payment_capture": "1"}
        )

        # Save the order in DB
        order = RazorpayPayment.objects.create(
            name=name, amount=amount, provider_order_id=razorpay_order["id"]
        )

        data = {
            "name" : name,
            "merchantId": RAZOR_KEY_ID,
            "amount": amount,
            "currency" : 'INR' ,
            "orderId" : razorpay_order["id"],
            }

        # save order Details to frontend
        return Response(data, status=status.HTTP_200_OK)

class RazorpayCallback(APIView):

    """
    APIView for Verifying Razorpay Order.
    :return: Success and failure response messages
    """

    @staticmethod
    def post(request, *args, **kwargs):

        # geting data form request
        response = request.data.dict()

        """
            if razorpay_signature is present in request
            it will try to verify
            else throw error_reason
        """
        if "razorpay_signature" in response:

            # Verifying Payment Signature
            data = razorpay_client.utility.verify_payment_signature(response)

            # if we get here Ture signature
            if data:
                payment_object = RazorpayPayment.objects.get(provider_order_id = response['razorpay_order_id'])                # razorpay_payment = RazorpayPayment.objects.get(order_id=response['razorpay_order_id'])
                payment_object.status = PaymentStatus.SUCCESS
                payment_object.payment_id = response['razorpay_payment_id']
                payment_object.signature_id = response['razorpay_signature']
                payment_object.save()

                return Response({'status': 'Payment Done'}, status=status.HTTP_200_OK)
            else:
                return Response({'status': 'Signature Mismatch!'}, status=status.HTTP_400_BAD_REQUEST)

        # Handling failed payments
        else:
            error_code = response['error[code]']
            error_description = response['error[description]']
            error_source = response['error[source]']
            error_reason = response['error[reason]']
            error_metadata = json.loads(response['error[metadata]'])

            razorpay_payment = RazorpayPayment.objects.get(provider_order_id=error_metadata['order_id'])
            razorpay_payment.payment_id = error_metadata['payment_id']
            razorpay_payment.signature_id = "None"
            razorpay_payment.status = PaymentStatus.FAILURE
            razorpay_payment.save()

            error_status = {
                'error_code': error_code,
                'error_description': error_description,
                'error_source': error_source,
                'error_reason': error_reason,
            }

            return Response({'error_data': error_status}, status=status.HTTP_401_UNAUTHORIZED)


def generate_api_key():
    characters = string.ascii_letters + string.digits + '!@#$%^&*()'
    while True:
        api_key = ''.join(random.choice(characters) for _ in range(10))
        api_key += str(uuid4())
        if not Company.objects.filter(api_key=api_key).exists():
            return api_key

@csrf_exempt
def generate_key_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        url = data.get('url')
        if name and url:
            api_key = generate_api_key()
            Company.objects.create(name=name, url=url, api_key=api_key)
            return JsonResponse({'api_key': api_key})
        else:
            return JsonResponse({'error': 'Please enter a company name and company URL.'}, status=400)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)


from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from .models import Company
import json

@csrf_exempt
def try_on(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        api_key = data.get('api_key')
        cloth_image = data.get('cloth_image')
        person_image = data.get('person_image')
        category = data.get('category')

        # Verify API key
        try:
            api_key_obj = Company.objects.get(api_key=api_key)
        except Company.DoesNotExist:
            return JsonResponse({'error': 'Invalid API key'}, status=401)

        # Validate inputs
        if not cloth_image or not person_image or not category:
            return HttpResponseBadRequest("Missing parameters")

        # Process the images and generate try-on result
        try_on_result = generate_try_on_result(cloth_image, person_image, category)

        if try_on_result.get('error'):
            return JsonResponse({'error': try_on_result['error']}, status=500)

        return JsonResponse({'try_on_result': try_on_result['images'][0]})

    return HttpResponseBadRequest("Invalid request method")

def save_base64_to_file(base64_string, extension):
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    # Convert base64 string to image data
    image_data = base64.b64decode(base64_string)
    temp_file = BytesIO(image_data)
    temp_image = Image.open(temp_file)

    # Use a temporary file and directory for safer handling
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
        temp_image.save(temp.name)
        return temp.name



def generate_try_on_result(cloth_image, person_image, category):
    cloth_image_path = None
    person_image_path = None
    human_image_path = None

    try:
        # Save base64 images to temporary files
        cloth_image_path = save_base64_to_file(cloth_image, '.png')
        person_image_path = save_base64_to_file(person_image, '.png')
        human_image_path = save_base64_to_file(person_image, '.png')

        # Load images
        garm_img = Image.open(cloth_image_path)
        human_img = Image.open(person_image_path)
        human_image = human_image_path
        # Save the original size of the person's image
        original_size = human_img.size

        # Prepare inputs
        dict_input = {"background": human_img}
        garment_des = str(category)
        is_checked = True
        is_checked_crop = False
        denoise_steps = 30
        seed = 42

        # Call start_tryon function
        output_image, mask_gray = start_tryon(dict_input, garm_img, garment_des,is_checked,is_checked_crop,denoise_steps,seed,human_image)

        # Resize the output image to the original size
        output_image_resized = output_image.resize(original_size, Image.LANCZOS)

        # Convert output images to base64
        buffered = BytesIO()
        output_image_resized.save(buffered, format="PNG")
        output_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return {'images': [output_base64]}

    except Exception as e:
        print(f"Error: {e}")
        return {'error': str(e)}
    finally:
        # Cleanup temporary files if needed
        if cloth_image_path:
            os.remove(cloth_image_path)
        if person_image_path:
            os.remove(person_image_path)
        if human_image_path:
            os.remove(human_image_path)

