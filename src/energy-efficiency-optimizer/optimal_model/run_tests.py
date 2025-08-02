import os

for n_users in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]:
    os.system("python3 run_model.py {}".format(n_users))