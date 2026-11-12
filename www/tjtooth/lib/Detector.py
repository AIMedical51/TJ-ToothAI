import cv2
import torch
import torch.nn.functional as F
import numpy as np
import cv2
from lib.Network_Res2Net_GRA_NCD import Network
from lib.mask2img  import generate_mask_img
from PIL import Image
import torchvision.transforms as transforms


class Detector(object):
    def __init__(self):
        self.img_size = 352
        self.model = Network(imagenet_pretrained=False)
        self.transform = transforms.Compose([
            transforms.Resize((self.img_size, self.img_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    def load_model(self, model_path):
        self.model.load_state_dict(torch.load(model_path,map_location='cpu'))
        # self.model.cuda() # 调用model.cuda()，可以将模型加载到GPU上
        self.model.eval() # 设置到预测模式

    def load_data(self, image_path):
        """
        接受一个rgb图像，返回图像的数组形式和Resize后的数组图像
        :param image_path:
        :return:
        """
        image = Image.open(image_path).convert('RGB')
        image_tensor = self.transform(image).unsqueeze(0)
        return image_tensor, np.array(image)

    # def load_data(self, image_path):
    #     image = Image.open(image_path).convert('RGB')
    #     preprocess = transforms.Compose([
    #         transforms.ToTensor(),
    #     ])
    #     image_tensor = preprocess(image).unsqueeze(0)
    #     return image_tensor, np.array(image)

    def predict(self, image, shape):
        """
        返回预测的结果，像素值0`1之间，大小为原图大小
        :param image:
        :param shape:
        :return:
        """
        # image = image.cuda()
        res5, res4, res3, res2 = self.model(image) # res3 ~ res5 没用
        res = res2
        res = F.upsample(res, size=shape[:-1], mode='bilinear', align_corners=False) # 双线性上采样至原图大小
        res = res.sigmoid().data.cpu().numpy().squeeze() # 降维
        res = (res - res.min()) / (res.max() - res.min() + 1e-8) # norm to 0~1
        return res

    def mask2img(self, res, rgb_image):
        """
        返回带有mask标注的图片
        :param res:
        :param rgb_image:
        :return:
        """
        res = res * 255
        ret, thresh = cv2.threshold(res, 230, 255, 0)
        mask_img = generate_mask_img(thresh)
        img_with_with_mask = mask_img * 0.8 + rgb_image
        img_with_with_mask[img_with_with_mask>255] = 255
        img_with_with_mask = img_with_with_mask.astype(np.uint8)
        return img_with_with_mask

    def write_frame(self, frame):
        """
        输入一张图片，得到带掩膜标注的图片
        :param frame:
        :return:
        """
        image, rgb_image = self.load_data(frame)
        res = self.predict(image, rgb_image.shape)
        img_with_mask = self.mask2img(res, rgb_image)
        return img_with_mask