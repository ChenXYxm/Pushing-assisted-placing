import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from prettytable import PrettyTable
from collections import namedtuple
import numpy as np
import random
import time
import pickle
import matplotlib.pyplot as plt
from torch.autograd import Variable
Transition = namedtuple("Transition", ("state", "action", "next_state", "reward"))

simple_Transition = namedtuple("simple_Transition", ("state", "action", "reward"))


def Transform_Image(means, stds):
    return T.Compose([T.ToTensor(), T.Normalize(means, stds)])


class ReplayBuffer(object):
    def __init__(self, size, simple=False):
        self.size = size
        self.memory = []
        self.position = 0
        self.simple = simple
        random.seed(20)

    def push(self, *args):
        if len(self.memory) < self.size:
            self.memory.append(None)
        if self.simple:
            self.memory[self.position] = simple_Transition(*args)
        else:
            self.memory[self.position] = Transition(*args)
        # If replay buffer is full, we start overwriting the first entries
        self.position = (self.position + 1) % self.size

    def sample(self, batch_size):
        rand_samples = random.sample(self.memory, batch_size - 1)
        rand_samples.append(self.memory[self.position - 1])
        return rand_samples

    def get(self, index):
        return self.memory[index]

    def __len__(self):
        return len(self.memory)


class CONV3_FC1(nn.Module):
    def __init__(self, h, w, outputs):
        super(CONV3_FC1, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=3)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=3)
        self.bn2 = nn.BatchNorm2d(32)
        # self.conv3 = nn.Conv2d(32, 64, kernel_size=5, stride=3)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=3)
        # self.bn3 = nn.BatchNorm2d(64)
        self.bn3 = nn.BatchNorm2d(32)

        def conv2d_size_out(size, kernel_size=5, stride=3):
            return (size - (kernel_size - 1) - 1) // stride + 1

        convw = conv2d_size_out(conv2d_size_out(conv2d_size_out(w)))
        convh = conv2d_size_out(conv2d_size_out(conv2d_size_out(h)))
        lin_input_size = convw * convh * 32
        fc1_output_size = int(np.round(outputs / 4))
        self.fc1 = nn.Linear(lin_input_size, outputs)

    def forward(self, x):
        # print(x.size())

        x = F.relu(self.bn1(self.conv1(x)))
        # print(x.size())
        x = F.relu(self.bn2(self.conv2(x)))
        # print(x.size())

        x = F.relu(self.bn3(self.conv3(x)))
        # print(x.size())
        return self.fc1(x.view(x.size(0), -1))


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(
        self,
        inplanes,
        planes,
        stride=1,
        downsample=None,
        groups=1,
        base_width=64,
        dilation=1,
        norm_layer=None,
    ):
        super(BasicBlock, self).__init__()
        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if groups != 1 or base_width != 64:
            raise ValueError("BasicBlock only supports groups=1 and base_width=64")
        if dilation > 1:
            raise NotImplementedError("Dilation > 1 not supported in BasicBlock")
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride)
        
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride
        if inplanes != planes:
            self.conv3 = nn.Conv2d(inplanes, planes, kernel_size=1, stride=1)
        else:
            self.conv3 = None

    def forward(self, x):
        identity = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        # if self.downsample is not None:
        # identity = self.downsample(x)

        if self.conv3:
            identity = self.conv3(identity)

        out += identity
        out = self.relu(out)

        return out


def conv3x3(in_planes, out_planes, stride=1, groups=1, dilation=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(
        in_planes,
        out_planes,
        kernel_size=3,
        stride=stride,
        padding=dilation,
        groups=groups,
        bias=False,
        dilation=dilation,
    )
def conv5x5(in_planes, out_planes, stride=1, groups=2, dilation=0):
    """3x3 convolution with padding"""
    return nn.Conv2d(
        in_planes,
        out_planes,
        kernel_size=5,
        stride=stride,
        padding=dilation,
        groups=groups,
        bias=False,
        dilation=dilation,
    )

class Perception_Module(nn.Module):
    def __init__(self):
        super(Perception_Module, self).__init__()
        # self.C1 = conv3x3(1, 64)
        # self.C0 = conv5x5(2, 32)
        # self.C1 = conv3x3(32, 64)
        self.C1 = conv3x3(2, 64)
        self.MP1 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.RB0 = BasicBlock(64, 64)
        self.RB1 = BasicBlock(64, 128)
        self.MP2 = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.RB2 = BasicBlock(128, 256)
        self.RB3 = BasicBlock(256, 512)

    def forward(self, x, verbose=0):
        if verbose == 1:
            print("### Perception Module ###")
            print("Input: ".ljust(15), x.size())
        # x = self.C0(x)
        # if verbose == 1:
        #     print("After Conv0: ".ljust(15), x.size())
        x = self.C1(x)
        if verbose == 1:
            print("After Conv1: ".ljust(15), x.size())
        x = self.MP1(x)
        if verbose == 1:
            print("After MP1: ".ljust(15), x.size())
        x = self.RB0(x)
        if verbose == 1:
            print("After RB0: ".ljust(15), x.size())
        x = self.RB1(x)
        if verbose == 1:
            print("After RB1: ".ljust(15), x.size())
        x = self.MP2(x)
        if verbose == 1:
            print("After MP2: ".ljust(15), x.size())
        x = self.RB2(x)
        if verbose == 1:
            print("After RB2: ".ljust(15), x.size())
        x = self.RB3(x)
        if verbose == 1:
            print("After RB3: ".ljust(15), x.size())

        return x

'''
class Grasping_Module(nn.Module):
    def __init__(self, output_activation="Sigmoid"):
        super(Grasping_Module, self).__init__()
        self.RB1 = BasicBlock(512, 256)
        self.RB2 = BasicBlock(256, 128)
        self.UP1 = nn.UpsamplingBilinear2d(scale_factor=2)
        self.RB3 = BasicBlock(128, 64)
        self.UP2 = nn.UpsamplingBilinear2d(scale_factor=2)
        self.C1 = nn.Conv2d(64, 1, kernel_size=1)
        self.output_activation = output_activation
        if self.output_activation is not None:
            self.sigmoid = nn.Sigmoid()

    def forward(self, x, verbose=0):
        if verbose == 1:
            print("### Grasping Module ###")
            print("Input: ".ljust(15), x.size())
        x = self.RB1(x)
        if verbose == 1:
            print("After RB1: ".ljust(15), x.size())
        x = self.RB2(x)
        if verbose == 1:
            print("After RB2: ".ljust(15), x.size())
        x = self.UP1(x)
        if verbose == 1:
            print("After UP1: ".ljust(15), x.size())
        x = self.RB3(x)
        if verbose == 1:
            print("After RB3: ".ljust(15), x.size())
        x = self.UP2(x)
        if verbose == 1:
            print("After UP2: ".ljust(15), x.size())
        x = self.C1(x)
        if verbose == 1:
            print("After C1: ".ljust(15), x.size())

        # x.requires_grad_(True)
        # x.register_hook(self.backward_gradient_hook)
        x.squeeze_()
        if verbose == 1:
            print("After Squeeze: ".ljust(15), x.size())
        if self.output_activation is not None:
            return self.sigmoid(x)
        else:
            return x
'''

class Grasping_Module_multidiscrete(nn.Module):
    def __init__(self, output_activation="Sigmoid", act_dim_2=1):
        super(Grasping_Module_multidiscrete, self).__init__()
        self.RB1 = BasicBlock(512, 256)
        self.RB2 = BasicBlock(256, 128)
        self.UP1 = nn.UpsamplingBilinear2d(scale_factor=2)
        self.RB3 = BasicBlock(128, 64)
        self.RB4 = BasicBlock(64, 64)
        self.UP2 = nn.UpsamplingBilinear2d(scale_factor=2)
        self.C1 = nn.Conv2d(64, act_dim_2, kernel_size=1)
        self.output_activation = output_activation
        if self.output_activation is not None:
            self.sigmoid = nn.Sigmoid()

    def forward(self, x, verbose=0):
        if verbose == 1:
            print("### Grasping Module ###")
            print("Input: ".ljust(15), x.size())
        x = self.RB1(x)
        if verbose == 1:
            print("After RB1: ".ljust(15), x.size())
        x = self.RB2(x)
        if verbose == 1:
            print("After RB2: ".ljust(15), x.size())
        x = self.UP1(x)
        if verbose == 1:
            print("After UP1: ".ljust(15), x.size())
        x = self.RB3(x)
        if verbose == 1:
            print("After RB3: ".ljust(15), x.size())
        x = self.RB4(x)
        if verbose == 1:
            print("After RB4: ".ljust(15), x.size())
        x = self.UP2(x)
        if verbose == 1:
            print("After UP2: ".ljust(15), x.size())
        x = self.C1(x)
        if verbose == 1:
            print("After C1: ".ljust(15), x.size())

        # x.requires_grad_(True)
        # x.register_hook(self.backward_gradient_hook)
        x.squeeze_()
        if verbose == 1:
            print("After Squeeze: ".ljust(15), x.size())
        if self.output_activation is not None:
            return self.sigmoid(x)
        else:
            return x

    def backward_gradient_hook(self, grad):
        """
        Hook for displaying the indices of non-zero gradients. Useful for making sure only
        the loss of pixels corresponding to selected actions get backpropagated.
        """

        print(
            f"Number of non zero gradients: {len([i for i,v in enumerate(grad.view(-1).cpu().numpy()) if v != 0])}"
        )


# def RESNET():
#     return nn.Sequential(Perception_Module(), Grasping_Module())


# def POLICY_RESNET():
#     return nn.Sequential(Perception_Module(), Grasping_Module(output_activation=None))

class MULTIDISCRETE_RESNET(nn.Module):
    def __init__(self,number_actions_dim_2) -> None:
        super().__init__()    
        self.features_extractor = Perception_Module()
        
        self.grasp_module = Grasping_Module_multidiscrete(act_dim_2=number_actions_dim_2)
        self.interm_feat = []
        self.output_prob = []
        if torch.cuda.is_available():
            self.use_cuda = True
        else:
            self.use_cuda = False
        
    ######################### rotate the original image ###########################
    def forward(self,x):
        self.output_prob = []
        self.interm_feat = []
        
        obs_tmp = x.clone().cpu()
        self.output = torch.zeros((len(obs_tmp),8,144,144),device='cuda')
        for rotate_idx in range(8):
            rotate_theta = -np.radians(rotate_idx*(360/8))

            # Compute sample grid for rotation BEFORE neural network
            affine_mat_before = np.asarray([[np.cos(-rotate_theta), np.sin(-rotate_theta), 0],[-np.sin(-rotate_theta), np.cos(-rotate_theta), 0]])
            affine_mat_before.shape = (2,3)
            affine_mat_before_tmp = np.zeros((2,3,len(obs_tmp)))
            for i in range(len(obs_tmp)):
                affine_mat_before_tmp[:,:,i] = affine_mat_before
            affine_mat_before = affine_mat_before_tmp
            affine_mat_before = torch.from_numpy(affine_mat_before).permute(2,0,1).float()
            # print(obs_tmp.size())
            if torch.cuda.is_available():
                flow_grid_before = F.affine_grid(Variable(affine_mat_before, requires_grad=False).cuda(), obs_tmp.size(),align_corners = False)
            else:
                flow_grid_before = F.affine_grid(Variable(affine_mat_before, requires_grad=False), obs_tmp.size(),align_corners = False)
            if self.use_cuda:
                rotate_obs = F.grid_sample(Variable(obs_tmp, requires_grad=False).cuda(), flow_grid_before, mode='nearest',align_corners = False)
                
            else:
                rotate_obs = F.grid_sample(Variable(obs_tmp, requires_grad=False), flow_grid_before, mode='nearest',align_corners = False)
            # plt.imshow(np.array(rotate_obs[0,1,:,:].clone().cpu())) 
            # plt.show()
            obs_feature = self.features_extractor(rotate_obs)
            obs_feature = self.grasp_module(obs_feature)
            # self.interm_feat.append(obs_feature)
            
            # plt.imshow(np.array(obs_feature[:,:].clone().cpu())) 
            # plt.show()
            # print(obs_feature.size())
            if obs_feature.dim() == 2:
                tmp_tensor = torch.zeros((1,1,144,144),device='cuda')
                tmp_tensor[0,0,:,:] = obs_feature
            else:
                tmp_tensor = torch.zeros((1,len(obs_feature),144,144),device='cuda')
                tmp_tensor[0,:,:,:] = obs_feature
                tmp_tensor=tmp_tensor.permute(1,0,2,3)
            # print('tmp_tensor:', tmp_tensor.size())
            affine_mat_after = np.asarray([[np.cos(rotate_theta), np.sin(rotate_theta), 0],[-np.sin(rotate_theta), np.cos(rotate_theta), 0]])
            affine_mat_after.shape = (2,3)
        
            affine_mat_after_tmp = np.zeros((2,3,len(obs_tmp)))
            for i in range(len(obs_tmp)):
                affine_mat_after_tmp[:,:,i] = affine_mat_after
            affine_mat_after = affine_mat_after_tmp
            affine_mat_after = torch.from_numpy(affine_mat_after).permute(2,0,1).float()
            if self.use_cuda:
                flow_grid_after = F.affine_grid(Variable(affine_mat_after, requires_grad=False).cuda(), tmp_tensor.size(),align_corners = False)
            else:
                flow_grid_after = F.affine_grid(Variable(affine_mat_after, requires_grad=False), tmp_tensor.size(),align_corners = False)
            obs_feature_rotated_back = F.grid_sample(tmp_tensor, flow_grid_after, mode='nearest',align_corners = False)
            # print('obs_rotate_bask_size: ',obs_feature_rotated_back.size())
            # self.output_prob.append(obs_feature_rotated_back)
            # fig, (ax1,ax2,ax3) = plt.subplots(1, 3, figsize=(7, 4))
            # ax1.imshow(np.array(rotate_obs[0,1,:,:].clone().cpu()))
            # ax2.imshow(np.array(tmp_tensor[0,0,:,:].clone().detach().cpu()))
            # ax3.imshow(np.array(obs_feature_rotated_back[0,0,:,:].clone().detach().cpu()))
            # plt.show()
            self.output[:,rotate_idx,:,:] = obs_feature_rotated_back[:,0,:,:]
            # print('out 1', self.output[:,rotate_idx,:,:].size(),obs_feature_rotated_back[:,0,:,:].size())
            # print('output_size: ',self.output.size())
        ###############################################################################
        # x = self.features_extractor(x)
        # x = self.grasp_module(x)
        del flow_grid_before,flow_grid_after,rotate_obs,obs_feature_rotated_back,obs_feature,tmp_tensor
        return self.output
# def MULTIDISCRETE_RESNET(number_actions_dim_2):
#     return nn.Sequential(
#         Perception_Module(), Grasping_Module_multidiscrete(act_dim_2=number_actions_dim_2)
#     )


def count_parameters(model):
    table = PrettyTable(["Modules", "Parameters"])
    total_params = 0
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        param = parameter.numel()
        table.add_row([name, param])
        total_params += param
    print(table)
    print(f"Total Trainable Params: {total_params} ({total_params/1000000:.2f}M)")

def rotate(obs,number_actions_dim_2=1):
    resnet = MULTIDISCRETE_RESNET(number_actions_dim_2)
    rotation = 4
    obs_tmp = obs.detach().clone()
    resnet_result = []
    for rotation_i in range(rotation):
        rotate_theta = np.radians(rotation_i*(360/rotation))
        affine_mat_before = np.asarray([[np.cos(-rotate_theta), np.sin(-rotate_theta), 0],[-np.sin(-rotate_theta), np.cos(-rotate_theta), 0]])
        affine_mat_before.shape = (2,3,1)
        affine_mat_before = torch.from_numpy(affine_mat_before).permute(2,0,1).float()
        flow_grid_before = F.affine_grid(Variable(affine_mat_before, requires_grad=False).cuda(), obs_tmp.size())
        rotate_obs = F.grid_sample(Variable(obs_tmp, volatile=True).cuda(), flow_grid_before, mode='nearest')
        resnet_out = resnet(rotate_obs)
        resnet_result.append(resnet_out.detach())
    return resnet_result



if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(device)
    resnet = MULTIDISCRETE_RESNET(1).cuda()
    # resnet = RESNET()

    test = torch.Tensor(3, 2, 144, 144).cuda()

    output = resnet(test)
    print(output.size(),output.view(3,-1).max(1))
    print(output.size(),output.view(3,-1).shape)
    output_np = output.cpu().detach().numpy()
    print(np.max(output_np),output_np.shape,np.unravel_index(np.argmax(output_np[0]),output_np.shape))
    count_parameters(resnet)
    plt.figure()
    for i in range(1,3):
        output_img = output_np[i].copy()
        index_tmp = np.unravel_index(np.argmax(output_img),output_img.shape)
        print(index_tmp,output_img.shape)
        output_img[index_tmp] = 1
        plt.subplot(1,4,i)
        plt.imshow(output_img[0])
    plt.show()
    test_1 = torch.zeros((3,2,144,144)).cuda().float()
    test_1[:,:,22:122,22:122] = 1.
    plt.figure()
    for i in range(1):
        output_img = test_1.cpu().detach().numpy()[i].copy()
        plt.subplot(1,3,i+1)
        plt.imshow(output_img[0])
    plt.show()
    angle = 45./180.*np.pi
    transform_matrix = torch.tensor([
        [np.cos(angle),np.sin(-angle),0],
        [np.sin(angle),np.cos(angle),0]
        ])
    transform_matrix = transform_matrix.unsqueeze(0).repeat(3,1,1).cuda().float()
    grid = F.affine_grid(transform_matrix,test_1.shape).cuda().float()
    output = F.grid_sample(test_1,grid,mode='nearest')
    plt.figure()
    for i in range(3):
        output_img = output.cpu().detach().numpy()[i].copy()
        plt.subplot(1,3,i+1)
        plt.imshow(output_img[0])
    plt.show()