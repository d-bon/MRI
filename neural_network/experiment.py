import torch
import torchvision
import torch.optim as optim
import matplotlib.pyplot as plt
import os
from datetime import datetime

from torch.utils.tensorboard import SummaryWriter

import training
from dataset import get_dataset
from neural_network_MRI import MRINetwork

# Get cpu or gpu device for training.
#device = "cuda" if torch.cuda.is_available() else "cpu"
device = "cuda"
print("Using {} device".format(device))

batch_size = 128
lr = 1e-3
epochs = 11

save_loss = False
generate_image = True

train_dataloader, test_dataloader = get_dataset(batch_size)

hdims = [256, 256]
input_dim = 256*256

loss = torch.nn.MSELoss()

# For adding graph in tensorboard
masked, raw = next(iter(train_dataloader))

model = MRINetwork(input_dim, hdims, loss)
model.double()

optimizer = optim.Adam(model.parameters(), lr=lr)

if generate_image or save_loss:

    # Name of the experiment
    name = "MRI_test"

    # We add a timestamp to the name
    date_now = datetime.now()
    path = date_now.strftime("_%H_%M_%S_%d_%b")
    path_1 = os.path.join(os.getcwd(), "runs")
    path = os.path.join(path_1, name + path)

    # And create a folder under the runs folder of that name
    # for the tensorboard files
    try:
        os.mkdir(path)
    except OSError as error: 
        try:
            os.mkdir(path + "_1")
        except OSError as error:
            print("help")

    # Tensorboard setup
    writer = SummaryWriter(path)
    writer.add_graph(model, masked)
    writer.close()

else:
    writer = None

model = model.to(device)

for i in range(epochs):
    print(f"Starting epoch {i}")
    training.training_loop(model, train_dataloader, test_dataloader, device, optimizer,
                                writer, i, save_loss, generate_image)

 