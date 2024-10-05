"""
Source code from https://github.com/hcw-00/STPM_pytorch_lightning.

Modifications: 
    - ...
    - ...
"""

import argparse
import torch
from torch.nn import functional as F
from torch import nn
from torchvision import transforms, datasets
from torchvision.utils import make_grid
from torch.utils.data import Dataset, DataLoader
import cv2
import numpy as np
import os
import glob
import shutil
import time
from torchvision.models import resnet18, resnet34
from PIL import Image
from sklearn.metrics import roc_auc_score
from torch import nn
import pytorch_lightning as pl
import string
import random
from sklearn.metrics import confusion_matrix
from pytorch_lightning.loggers import WandbLogger
####
import matplotlib.pyplot as plt
from kornia import image_to_tensor, tensor_to_image
from kornia.augmentation import RandomBoxBlur, ColorJiggle, Normalize, RandomAffine, CenterCrop, Resize
from torch import Tensor
import wandb
####

def copy_files(src, dst, ignores=[]):
    src_files = os.listdir(src)
    for file_name in src_files:
        ignore_check = [True for i in ignores if i in file_name]
        if ignore_check:
            continue
        full_file_name = os.path.join(src, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, os.path.join(dst,file_name))
        if os.path.isdir(full_file_name):
            os.makedirs(os.path.join(dst, file_name), exist_ok=True)
            copy_files(full_file_name, os.path.join(dst, file_name), ignores)

def prep_dirs(root):
    # TODO: We could delete this part. 
    # make sample dir
    sample_path = os.path.join(root, 'sample')
    os.makedirs(sample_path, exist_ok=True)
    # make source code record dir & copy
    source_code_save_path = os.path.join(root, 'src')
    os.makedirs(source_code_save_path, exist_ok=True)
    copy_files('./', source_code_save_path, ['.git','.vscode','__pycache__','logs','README','samples','LICENSE', 'data']) # copy source code
    return sample_path, source_code_save_path

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def auto_select_weights_file(weights_file_version):
    print()
    version_list = glob.glob(args.project_path + '/STPM/')
    version_list.sort(reverse=True, key=lambda x: os.path.getmtime(x))
    if weights_file_version != None:
        version_list = [args.project_path + '/STPM/' + weights_file_version]
    for i in range(len(version_list)):
        # if os.path.exists(os.path.join(version_list[i],'checkpoints')):
        weights_file_path = glob.glob(os.path.join(version_list[i],'checkpoints')+'/*')
        if len(weights_file_path) == 0:
            if weights_file_version != None and i == 0:
                print(f'Checkpoint of {weights_file_version} not found')
            continue
        else:
            weights_file_path = weights_file_path[0]
            if weights_file_path.split('.')[-1] != 'ckpt':
                continue
        print('Checkpoint found : ', weights_file_path)
        print()
        return weights_file_path
    print('Checkpoint not found')
    print()
    return None

#imagenet
mean_train = [0.485, 0.456, 0.406]
std_train = [0.229, 0.224, 0.225]


class DataAugmentation(nn.Module):
    """Module to perform data augmentation using Kornia on torch tensors."""

    def __init__(self, apply_color_jitter: bool = False) -> None:
        super().__init__()
        self._apply_color_jitter = apply_color_jitter

        self.transforms = nn.Sequential(
            RandomBoxBlur(kernel_size=(2,2), border_type='reflect', p=0.2),
            RandomBoxBlur(kernel_size=(3,3), border_type='reflect', p=0.2),
            #RandomBoxBlur(kernel_size=(5,5), border_type='reflect', p=0.2),
            #RandomBoxBlur(kernel_size=(7,7), border_type='reflect', p=0.2),
            #RandomBoxBlur(kernel_size=(5,5), border_type='reflect', p=0.2),
            #RandomBoxBlur(kernel_size=(15,15), border_type='reflect', p=0.1),
            #RandomAffine(degrees=45.0, scale=(1,2), padding_mode=2, p=.75),
            #ColorJiggle(0.1, 0.1, 0.1, 0.1, p=1.),
        )

    @torch.no_grad()  # disable gradients for effiency
    def forward(self, x: Tensor) -> Tensor:
        x_out = self.transforms(x)  # BxCxHxW
        if self._apply_color_jitter:
            x_out = self.jitter(x_out)
        return x_out


class MVTecDataset(Dataset):
    def __init__(self, root, transform=None, input_size=None, phase=None):
        if phase=='train':
            self.img_path = os.path.join(root, 'train')
        else:
            self.img_path = os.path.join(root, 'test')
            self.gt_path = os.path.join(root, 'ground_truth')
        self.transform = transform
        self.input_size = input_size
        # load dataset
        self.img_paths, self.gt_paths, self.labels, self.types = self.load_dataset() # self.labels => good : 0, anomaly : 1

    def load_dataset(self):

        img_tot_paths = []
        gt_tot_paths = []
        tot_labels = []
        tot_types = []

        defect_types = os.listdir(self.img_path)
        
        for defect_type in defect_types:
            if defect_type == 'good':
                img_paths = glob.glob(os.path.join(self.img_path, defect_type) + "/*.png")
                img_tot_paths.extend(img_paths)
                gt_tot_paths.extend([0]*len(img_paths))
                tot_labels.extend([0]*len(img_paths))
                tot_types.extend(['good']*len(img_paths))
            else:
                img_paths = glob.glob(os.path.join(self.img_path, defect_type) + "/*.png")
                gt_paths = glob.glob(os.path.join(self.gt_path, defect_type) + "/*.png")
                img_paths.sort()
                gt_paths.sort()
                img_tot_paths.extend(img_paths)
                gt_tot_paths.extend(gt_paths)
                tot_labels.extend([1]*len(img_paths))
                tot_types.extend([defect_type]*len(img_paths))

        assert len(img_tot_paths) == len(gt_tot_paths), "Something wrong with test and ground truth pair!"
        
        return img_tot_paths, gt_tot_paths, tot_labels, tot_types

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx):
        img_path, gt, label, img_type = self.img_paths[idx], self.gt_paths[idx], self.labels[idx], self.types[idx]
        img = Image.open(img_path).convert('RGB')
        img = self.transform(img)
        if gt == 0:
            gt = torch.zeros([1, self.input_size, self.input_size])
        else:
            gt = Image.open(gt)
            gt = gt.resize((self.input_size, self.input_size))
            gt = transforms.ToTensor()(gt)
        
        return img, gt, label, os.path.basename(img_path[:-4]), img_type

def show_cam_on_image(img, anomaly_map):
    heatmap = cv2.applyColorMap(np.uint8(anomaly_map), cv2.COLORMAP_JET)
    cam = np.float32(heatmap) + np.float32(img)
    cam = cam / np.max(cam)
    return np.uint8(255 * cam)

def cvt2heatmap(gray):
    heatmap = cv2.applyColorMap(np.uint8(gray), cv2.COLORMAP_JET)
    return heatmap

def heatmap_on_image(heatmap, image):
    out = np.float32(heatmap)/255 + np.float32(image)/255
    out = out / np.max(out)
    return np.uint8(255 * out)

def min_max_norm(image):
    a_min, a_max = image.min(), image.max()
    return (image-a_min)/(a_max - a_min)    

def init_weights(m):
    if type(m) == nn.Conv2d:
        torch.nn.init.xavier_uniform(m.weight)

def cal_confusion_matrix(y_true, y_pred_no_thresh, thresh, img_path_list):
    pred_thresh = []
    false_n = []
    false_p = []
    for i in range(len(y_pred_no_thresh)):
        if y_pred_no_thresh[i] > thresh:
            pred_thresh.append(1)
            if y_true[i] == 0:
                false_p.append(img_path_list[i])
        else:
            pred_thresh.append(0)
            if y_true[i] == 1:
                false_n.append(img_path_list[i])

    cm = confusion_matrix(y_true, pred_thresh)
    wandb.sklearn.plot_confusion_matrix(pred_thresh, y_true) 
    #wandb.log({"roc_img_level" : wandb.plot.roc_curve(np.squeeze(np.asarray(y_true)), np.squeeze(np.asarray(pred_thresh)))})
    #wandb.log({"prec_recall_img_level":wandb.plot.pr_curve(y_true, pred_thresh)})
    dpred = np.asarray(y_pred_no_thresh)
    binary_encoded = np.where(dpred > thresh, 1, 0)
    false_positive = np.logical_and(binary_encoded, np.logical_not(y_true))
    false_negative = np.logical_and(np.logical_not(binary_encoded), y_true)
    

    arr = dpred[false_negative]
    if len(arr)!= 0: 
      print("For false negative:")
      print("\tMean:", np.mean(arr))
      print("\tMedian:", np.median(arr))
      print("\tMax:", np.max(arr))
      print("\tMin:", np.min(arr))
      print("\tamount:", len(arr))
    else: 
      print("No false negative")

    arr2 = dpred[false_positive]
    if len(arr2) != 0:
      print("For false positive:")
      print("\tMean:", np.mean(arr2))
      print("\tMedian:", np.median(arr2))
      print("\tMax:", np.max(arr2))
      print("\tMin:", np.min(arr2))
      print("\tamount:", len(arr2))
    else: 
      print("No false positive")

    print('false positive')
    print(false_p)
    print('false negative')
    print(false_n)
    

class STPM(pl.LightningModule):
    def __init__(self, hparams):
        super(STPM, self).__init__()

        self.save_hyperparameters(hparams)

        self.init_features()
        def hook_t(module, input, output):
            self.features_t.append(output)
        def hook_s(module, input, output):
            self.features_s.append(output)

        self.model_t = resnet18(weights='ResNet18_Weights.DEFAULT').eval()
        for param in self.model_t.parameters():
            param.requires_grad = False

        self.model_t.layer1[-1].register_forward_hook(hook_t)
        self.model_t.layer2[-1].register_forward_hook(hook_t)
        self.model_t.layer3[-1].register_forward_hook(hook_t)

        self.model_s = resnet18(weights=None) # default: False
        # self.model_s.apply(init_weights)
        self.model_s.layer1[-1].register_forward_hook(hook_s)
        self.model_s.layer2[-1].register_forward_hook(hook_s)
        self.model_s.layer3[-1].register_forward_hook(hook_s)

        self.criterion = torch.nn.MSELoss(reduction='sum')

        self.gt_list_px_lvl = []
        self.pred_list_px_lvl = []
        self.gt_list_img_lvl = []
        self.pred_list_img_lvl = []
        self.img_path_list = []

        self.transform = DataAugmentation()  # per batch augmentation_kornia

        self.data_transforms = transforms.Compose([
                        transforms.Resize((args.load_size, args.load_size), transforms.InterpolationMode.LANCZOS),
                        transforms.ToTensor(),
                        transforms.CenterCrop(args.input_size),
                        transforms.Normalize(mean=mean_train,
                                            std=std_train)])
        self.inv_normalize = transforms.Normalize(mean=[-0.485/0.229, -0.456/0.224, -0.406/0.255], std=[1/0.229, 1/0.224, 1/0.255])



    def show_batch(self, win_size=(10, 10)):
        def _to_vis(data):
            return tensor_to_image(make_grid(data, nrow=8))

        # get a batch from the training set: try with `val_datlaoader` :)
        print("dbuuug", len(next(iter(self.train_dataloader()))))
        imgs, labels, _, _, _ = next(iter(self.train_dataloader()))
        print(imgs.shape)
        imgs_aug = self.transform(imgs)  # apply transforms
        # use matplotlib to visualize
        plt.figure(figsize=win_size)
        plt.imshow(_to_vis(imgs))
        plt.savefig('img_before_augment.png',  bbox_inches='tight')
        plt.figure(figsize=win_size)
        plt.imshow(_to_vis(imgs_aug))
        plt.savefig('img_augment.png', bbox_inches='tight')

    def on_after_batch_transfer(self, batch, dataloader_idx):
        x, gt, label, file_name, x_type = batch
        if self.trainer.training:
            x = self.transform(x)  # => we perform GPU/Batched data augmentation
        return x, gt, label, file_name, x_type

    def init_features(self):
        self.features_t = []
        self.features_s = []

    def forward(self, x):
        self.init_features()
        x_t = self.model_t(x)
        x_s = self.model_s(x)
        return self.features_t, self.features_s

    def cal_loss(self, fs_list, ft_list):
        tot_loss = 0
        for i in range(len(ft_list)):
            fs = fs_list[i]
            ft = ft_list[i]
            _, _, h, w = fs.shape
            fs_norm = F.normalize(fs, p=2)
            ft_norm = F.normalize(ft, p=2)
            f_loss = (0.5/(w*h))*self.criterion(fs_norm, ft_norm)
            tot_loss += f_loss
            
        return tot_loss
    
    def cal_anomaly_map(self, fs_list, ft_list, out_size=224):
        if args.amap_mode == 'mul':
            anomaly_map = np.ones([out_size, out_size])
        else:
            anomaly_map = np.zeros([out_size, out_size])
        a_map_list = []
        for i in range(len(ft_list)):
            fs = fs_list[i]
            ft = ft_list[i]
            fs_norm = F.normalize(fs, p=2)
            ft_norm = F.normalize(ft, p=2)
            a_map = 1 - F.cosine_similarity(fs_norm, ft_norm)
            a_map = torch.unsqueeze(a_map, dim=1)
            a_map = F.interpolate(a_map, size=out_size, mode='bilinear')
            a_map = a_map[0,0,:,:].to('cpu').detach().numpy()
            a_map_list.append(a_map)
            if args.amap_mode == 'mul':
                anomaly_map *= a_map
            else:
                anomaly_map += a_map
        return anomaly_map, a_map_list

    def save_anomaly_map(self, anomaly_map, a_maps, input_img, gt_img, file_name, x_type):
        anomaly_map_norm = min_max_norm(anomaly_map)
        anomaly_map_norm_hm = cvt2heatmap(anomaly_map_norm*255)
        # 64x64 map
        am64 = min_max_norm(a_maps[0])
        am64 = cvt2heatmap(am64*255)
        # 32x32 map
        am32 = min_max_norm(a_maps[1])
        am32 = cvt2heatmap(am32*255)
        # 16x16 map
        am16 = min_max_norm(a_maps[2])
        am16 = cvt2heatmap(am16*255)
        # anomaly map on image
        heatmap = cvt2heatmap(anomaly_map_norm*255)
        hm_on_img = heatmap_on_image(heatmap, input_img)

        # save images
        # file_name = id_generator() # random id
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}.jpg'), input_img)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_am64.jpg'), am64)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_am32.jpg'), am32)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_am16.jpg'), am16)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_amap.jpg'), anomaly_map_norm_hm)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_amap_on_img.jpg'), hm_on_img)
        cv2.imwrite(os.path.join(self.sample_path, f'{x_type}_{file_name}_gt.jpg'), gt_img)

    def configure_optimizers(self):
        return torch.optim.SGD(self.model_s.parameters(), lr=args.lr, momentum=args.momentum, weight_decay=args.weight_decay)

    def train_dataloader(self):
        image_datasets = MVTecDataset(root=os.path.join(args.dataset_path,args.category), transform=self.data_transforms, input_size=args.load_size, phase='train')
        train_loader = DataLoader(image_datasets, batch_size=args.batch_size, shuffle=True, num_workers=4) #, pin_memory=True)
        return train_loader

    def test_dataloader(self):
        test_datasets = MVTecDataset(root=os.path.join(args.dataset_path,args.category), transform=self.data_transforms, input_size=args.load_size, phase='test')
        test_loader = DataLoader(test_datasets, batch_size=1, shuffle=False, num_workers=4) #, pin_memory=True) # only work on batch_size=1, now.
        return test_loader

    def on_train_start(self):
        self.model_t.eval() # to stop running_var move (maybe not critical)
        #shutil.copy("train_resnet.py", self.logger.save_dir)
        #self.sample_path, self.source_code_save_path = prep_dirs(self.logger.save_dir)
        self.sample_path = 'sample'
        os.makedirs(self.sample_path, exist_ok=True)
    
    def on_test_start(self):
        #self.sample_path, self.source_code_save_path = prep_dirs(self.logger.save_dir)
        #shutil.copy("train_resnet.py", self.logger.save_dir)
        self.sample_path = "sample"
        os.makedirs(self.sample_path, exist_ok=True)

    def training_step(self, batch, batch_idx):
        x, _, _, file_name, _ = batch
        features_t, features_s = self(x)
        loss = self.cal_loss(features_s, features_t)
        self.log('train_loss', loss, on_epoch=True, batch_size=args.batch_size)
        return loss

    def test_step(self, batch, batch_idx):
        x, gt, label, file_name, x_type = batch
        features_t, features_s = self(x)
        
        # Get anomaly map
        anomaly_map, a_map_list = self.cal_anomaly_map(features_s, features_t, out_size=args.input_size)
        
        gt = transforms.CenterCrop(args.input_size)(gt)
        gt_np = gt.cpu().numpy().astype(int)
        self.gt_list_px_lvl.extend(gt_np.ravel())
        self.pred_list_px_lvl.extend(anomaly_map.ravel())
        self.gt_list_img_lvl.append(label.cpu().numpy()[0])
        self.pred_list_img_lvl.append(anomaly_map.max())
        self.img_path_list.append(''.join(map(lambda x: str(x or ''), x_type + tuple('_') + file_name)))
        # save images
        x = self.inv_normalize(x)
        input_x = cv2.cvtColor(x.permute(0,2,3,1).cpu().numpy()[0]*255, cv2.COLOR_BGR2RGB)
        self.save_anomaly_map(anomaly_map, a_map_list, input_x, gt_np[0][0]*255, file_name[0], x_type[0])

    def test_epoch_end(self, outputs):
        print("Total pixel-level auc-roc score :")
        pixel_auc = roc_auc_score(self.gt_list_px_lvl, self.pred_list_px_lvl, average='weighted')
        #wandb.log({"roc_pixel_level" : wandb.plot.roc_curve( self.gt_list_px_lvl, self.pred_list_px_lvl)})
        #wandb.log({"prec_recall_pixel_level":wandb.plot.pr_curve(self.gt_list_px_lvl, self.pred_list_px_lvl, labels=None, classes_to_plot=None)})

        print(pixel_auc)
        print("Total image-level auc-roc score :")
        img_auc = roc_auc_score(self.gt_list_img_lvl, self.pred_list_img_lvl, average='weighted')
        print(img_auc)
        print('test_epoch_end')
        values = {'pixel_auc': pixel_auc, 'img_auc': img_auc}
        wandb.run.summary["pixel_auc"] = pixel_auc
        wandb.run.summary["img_auc"] = img_auc
        self.log_dict(values)
        # 값 분리
        anomaly_list = []
        normal_list = []
        for i in range(len(self.gt_list_img_lvl)):
            if self.gt_list_img_lvl[i] == 1:
                anomaly_list.append(self.pred_list_img_lvl[i])
            else:
                normal_list.append(self.pred_list_img_lvl[i])

        # thresholding
        cal_confusion_matrix(self.gt_list_img_lvl, self.pred_list_img_lvl, img_path_list = self.img_path_list, thresh = args.thresh)
        #wandb.sklearn.plot_confusion_matrix(self.gt_list_img_lvl, self.pred_list_img_lvl, nb.classes_) 
        print()
        #with open(args.project_path + r'results.txt', 'a') as f:
            #f.write(self.logger.log_dir + '\n')
            #f.write(args.category + ' : ' + str(values) + '\n')


def get_args():
    parser = argparse.ArgumentParser(description='ANOMALYDETECTION')
    parser.add_argument('--phase', choices=['train','test', 'augment'], default='train')
    parser.add_argument('--dataset_path', default=r'data') #/tile') #'D:\Dataset\REVIEW_BOE_HKC_WHTM\REVIEW_for_anomaly\HKC'
    parser.add_argument('--category', default='carpet')
    parser.add_argument('--num_epochs', default=50, type=int)
    parser.add_argument('--thresh', default=0.00097, type=float)
    parser.add_argument('--lr', default=0.4)
    parser.add_argument('--momentum', default=0.9)
    parser.add_argument('--weight_decay', default=0.0001)
    parser.add_argument('--batch_size', default=32)
    parser.add_argument('--load_size', default=256) # 256
    parser.add_argument('--input_size', default=256)
    parser.add_argument('--project_path', default='/content/STPM-Unet-for-industrial-anomaly-detection') #210605') # TODO: what is it for ? It is for taking the checkpoint data
    parser.add_argument('--save_src_code', default=True)
    parser.add_argument('--save_anomaly_map', default=True)
    parser.add_argument('--amap_mode', choices=['mul','sum'], default='mul')
    parser.add_argument('--weights_file_version', type=str, default='') # Put a random generator name of checkpoint version
    parser.add_argument('--from_wandb_run', type=str, default=None)
    args = parser.parse_args()
    return args

if __name__ == '__main__':

    wandb_logger = WandbLogger(project="STPM", entity="stpm-unet")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args = get_args()
    
    trainer = pl.Trainer.from_argparse_args(args, default_root_dir=os.path.join(args.project_path, args.category), max_epochs=args.num_epochs, accelerator='gpu', devices=1,  logger=wandb_logger) #, check_val_every_n_epoch=args.val_freq,  num_sanity_val_steps=0) # ,fast_dev_run=True)
    
    if args.phase == 'train':
        model = STPM(hparams=args)
        trainer.fit(model)
        trainer.test(model)
        wandb.save("model.h5")
    elif args.phase == 'test':
        # selet weights file.
        weights_file_path = auto_select_weights_file(args.weights_file_version) # auto select if args.weights_file_version == None
        
        if weights_file_path != None:
            model = STPM(hparams=args).load_from_checkpoint(weights_file_path)
            # model.load_from_checkpoint(weights_file_path) # separating "load_from_checkpoint" seems does not load weights properly.
            trainer.test(model)
        else:
            print('Weights file is not found!')
    elif args.phase == 'augment':
        model = STPM(hparams=args)
        model.show_batch(win_size=(14, 14))
