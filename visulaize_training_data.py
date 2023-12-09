import os
import matplotlib.pyplot as plt
import pickle as pkl
import numpy as np
file_list = os.listdir("training_data/")
for i in file_list:
    print(i)
    # env_path = "training_data/"+'training_data47.pkl'
    env_path = "training_data/"+i
    fileObject = open(env_path, 'rb')
    data =  pkl.load(fileObject)
    for j in data:
        '''
        [actions,clipped_actions,self._last_obs,
        new_obs.cpu().numpy(),rewards.cpu().numpy(),dones.cpu().numpy(),infos]
        '''
        print(data[j][0],data[j][1])
        # print(data[j][0].shape)
        print(data[j][2].shape)
        print(data[j][4])
        image_tmp = np.squeeze(data[j][2].copy())
        image_post_tmp = np.squeeze(data[j][3].copy())
        image_post_tmp_1 = np.squeeze(data[j][9].copy())
        for k in range(data[j][2].shape[0]):
            fig, (ax1,ax4,ax2,ax3) = plt.subplots(1, 4, figsize=(15, 10))
            image_add_act = image_tmp[k].copy()
            image_add_act[data[j][0][k][0],data[j][0][k][1]] = 100
            ax1.imshow(image_tmp[k])
            ax2.imshow(image_post_tmp[k])
            ax3.imshow(image_post_tmp_1[k])
            ax4.imshow(image_add_act)
            # f, axarr = plt.subplots(2,2)
            # axarr[0,0].imshow(image_tmp[k])
            # axarr[0,1].imshow(image_post_tmp[k])
            plt.show()
            