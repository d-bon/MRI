import matplotlib.pyplot as plt
import numpy as np
from skimage import io

import torch
from torch import nn
import torchvision

# This is very ugly im sorry 
import sys
# insert at 1, 0 is the script path (or '' in REPL)
sys.path.insert(1, r"C:\Users\daan\Desktop\TUe\Master year 1\Master Math\Inverse Problems and Imaging\report\mri_regularization")

import update_method, cost

class MRIConvolutionalNetwork(nn.Module):
    """ Convolutional Neural Network """

    def __init__(self, device):
        super(MRIConvolutionalNetwork, self).__init__()

        self.build_loss()
        self.device = device

        self.network = nn.Sequential(
            nn.Conv2d(1, 40, 9, padding=4),
            # nn.BatchNorm2d(10),
            nn.ReLU(),
            nn.Conv2d(40, 32, 5, padding=2),
            # nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 1, 5, padding=2),
            nn.ReLU()
        )

    def __str__(self):
        return " Convolutional denoising network "

    def forward(self, x):
        """
        Forward pass through the network
        """
        return self.network(x)

    def build_loss(self):
        self.MSE_loss = nn.MSELoss()
        self.L1_reg = nn.L1Loss(reduction="sum")
        self.lam = 1e-3

    def loss_function(self, x, y):
        """
            X is prediction, Y is true value
        """
        # temp = torch.zeros(x.size()).to(self.device)
        return self.MSE_loss(x,y) 
        # + self.lam * self.L1_reg(temp, x)

    def _calculate_mask(self, sub_image_size=40, stride=12):
        self.mask = torch.zeros(256,256)

        for i in range((256 - sub_image_size)//stride + 1):
            for j in range((256 - sub_image_size)//stride + 1):
                lower_index_x = i*stride
                upper_index_x = i*stride + sub_image_size

                lower_index_y = j*stride
                upper_index_y = j*stride + sub_image_size
                
                self.mask[lower_index_x:upper_index_x, lower_index_y:upper_index_y] += 1

    def reconstruct_full_image(self, full_img_batch, noisy_img_batch, writer, device, sub_image_size=40, stride=12):
        """
            Reconstruct images using only the neural network
        """
        n = min(full_img_batch.size(0), 16)
        result = torch.zeros(n,1,256,256)

        self._calculate_mask(sub_image_size, stride)

        with torch.no_grad():
            for index in range(n):
                img = noisy_img_batch[index, 0]

                for i in range((img.shape[0] - sub_image_size)//stride + 1):
                    for j in range((img.shape[1] - sub_image_size)//stride + 1):
                        lower_index_x = i*stride
                        upper_index_x = i*stride + sub_image_size

                        lower_index_y = j*stride
                        upper_index_y = j*stride + sub_image_size
                        sub_image = torch.zeros(1,1,40,40, dtype=torch.double)
                        sub_image[0,0] = img[lower_index_x:upper_index_x, lower_index_y:upper_index_y]
                        sub_image = sub_image.to(device)

                        denoised_image = self.forward(sub_image)
                        denoised_image = denoised_image.cpu()

                        result[index, 0, lower_index_x:upper_index_x, lower_index_y:upper_index_y] += denoised_image[0,0]
                
                result[index, 0] /= self.mask

                # Normalize for Tensorboard
                result[index, 0] /= torch.max(result[index, 0])
                full_img_batch[index, 0] /= torch.max(full_img_batch[index, 0])
                noisy_img_batch[index, 0] /= torch.max(noisy_img_batch[index,0])

        comparison = torch.cat([full_img_batch[:n], noisy_img_batch[:n],
                                result])

        img_grid = torchvision.utils.make_grid(comparison.cpu(), nrows=2)
        writer.add_image(f"Original images and neural network denoising", img_grid) 
        writer.close()

        # If we want to further use the reconstructed images
        return result


    def reconstruct_full_image_reg(self, full_img_batch, noisy_img_batch, writer, device, sub_image_size=40, stride=12):
        """
            Reconstruct images using first the neural network, and then perform gradient descent on a least squares problem
            using the reconstruction as initial guess
        """

        n = min(full_img_batch.size(0), 8)
        result = torch.zeros(n,1,256,256)
        result_2 = torch.zeros(n,1,256,256)

        # We first pass it through the neural network to obtained denoised images
        denoised_nn_images = self.reconstruct_full_image(full_img_batch, noisy_img_batch, writer, device, sub_image_size, stride)
        denoised_nn_images = denoised_nn_images.numpy()

        # We then run gradient descent on each of these images for several iterations
        # Parameters for the gradient descent
        learning_rate = 5e-6
        max_iter = 2000
        lam = 0.04
        alpha = 0.02

        for i in range(denoised_nn_images.shape[0]):
            print(f"Denoising image {i}")
            fourier_trans = cost.undersample_fourier(full_img_batch[i,0])
            img = denoised_nn_images[i,0]
            img = img/np.max(np.abs(img))

            test_img = noisy_img_batch[i,0].numpy()
            test_img = test_img/np.max(np.abs(test_img))

            result[i, 0] = torch.from_numpy(update_method.gradient_descent(fourier_trans, lam, alpha, max_iter, learning_rate, img))
            result_2[i, 0] = torch.from_numpy(update_method.gradient_descent(fourier_trans, lam, alpha, max_iter, learning_rate, test_img))

            # Normalize for Tensorboard, otherwise images wont display correctly
            result[i, 0] /= torch.max(result[i, 0])
            full_img_batch[i, 0] /= torch.max(full_img_batch[i, 0])
            noisy_img_batch[i, 0] /= torch.max(noisy_img_batch[i,0])
            result_2[i, 0] /= torch.max(result_2[i, 0])

        comparison = torch.cat([full_img_batch[:n], noisy_img_batch[:n],
                                result])

        comparison_2 = torch.cat([full_img_batch[:n], noisy_img_batch[:n],
                                result_2])

        comparison_3 = torch.cat([full_img_batch[:n], result,
                                result_2])

        img_grid = torchvision.utils.make_grid(comparison.cpu(), nrows=3)
        img_grid_2 = torchvision.utils.make_grid(comparison_2.cpu(), nrows=3)
        img_grid_3 = torchvision.utils.make_grid(comparison_3.cpu(), nrows=3)

        writer.add_image(f"Original images and neural network + reg denoising", img_grid) 
        writer.add_image(f"Original images and reg denoising", img_grid_2) 
        writer.add_image(f"Comparison denoising", img_grid_3)

        writer.close()

        return result

    def reconstruct_full_image_reg_2(self, full_img_batch, noisy_img_batch, writer, device, sub_image_size=40, stride=12):
        """
            Reconstruct images using a neural network and a least squares problem incorporating the denoises image as regularization term
        """

        # Create the arrays to store the results in
        n = min(full_img_batch.size(0), 8)
        result = torch.zeros(n,1,256,256)
        result_2 = torch.zeros(n,1,256,256)

        # We first pass it through the neural network to obtained denoised images
        # This also saves it to tensorboard
        denoised_nn_images = self.reconstruct_full_image(full_img_batch, noisy_img_batch, writer, device, sub_image_size, stride)
        denoised_nn_images = denoised_nn_images.numpy()

        # We then run gradient descent on each of these images for several iterations
        # Parameters for the gradient descent where we use the denoised image as initial guess
        learning_rate_1 = 8e-6
        max_iter_1 = 2000
        lam_1 = 0.02
        alpha_1 = 0.02

        # Parameters for the gradient descent where we use the denoised image as additional regularizer
        learning_rate_2 = 8e-6
        max_iter_2 = 2000
        lam_2 = 0.02
        alpha_2 = 0.02

        # Loop over the examples
        for i in range(denoised_nn_images.shape[0]):
            print(f"Denoising image {i}")
            
            # Create the data needed for gradient descent
            full_img_batch[i, 0] /= torch.max(full_img_batch[i, 0])
            noisy_img_batch[i, 0] /= torch.max(noisy_img_batch[i,0])
            fourier_trans = cost.undersample_fourier(full_img_batch[i,0])

            # We use this as initial guess for the gradient descent
            img = denoised_nn_images[i,0]
            img = img/np.max(np.abs(img))

            result[i, 0] = torch.from_numpy(update_method.gradient_descent(fourier_trans, lam_1, alpha_1, max_iter_1, learning_rate_1, img))
            result_2[i, 0] = torch.from_numpy(update_method.gradient_descent_nn(fourier_trans, img, lam_2, alpha_2, max_iter_2, learning_rate_2, noisy_img_batch[i, 0].numpy()))

            # Normalize for Tensorboard, otherwise images wont display correctly
            result[i, 0] /= torch.max(result[i, 0])
            result_2[i, 0] /= torch.max(result_2[i, 0])

        comparison = torch.cat([full_img_batch[:n], noisy_img_batch[:n],
                                result])

        comparison_2 = torch.cat([full_img_batch[:n], noisy_img_batch[:n],
                                result_2])

        img_grid = torchvision.utils.make_grid(comparison.cpu(), nrows=3)
        img_grid_2 = torchvision.utils.make_grid(comparison_2.cpu(), nrows=3)

        writer.add_image(f"Original images and neural network + gradient descent", img_grid) 
        writer.add_image(f"Original images and neural network + reg denoising", img_grid_2) 

        writer.close()

        return result, result_2


if __name__ == "__main__":
    pass