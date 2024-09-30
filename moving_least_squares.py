import cv2
import numpy as np
import gradio as gr

# 初始化全局变量，存储控制点和目标点
points_src = []
points_dst = []
image = None

# 上传图像时清空控制点和目标点
def upload_image(img):
    global image, points_src, points_dst
    points_src.clear()  # 清空控制点
    points_dst.clear()  # 清空目标点
    image = img
    return img

# 记录点击点事件，并标记点在图像上，同时在成对的点间画箭头
def record_points(evt: gr.SelectData):
    global points_src, points_dst, image
    x, y = evt.index[0], evt.index[1]  # 获取点击的坐标
    
    # 判断奇偶次来分别记录控制点和目标点
    if len(points_src) == len(points_dst):
        points_src.append([x, y])  # 奇数次点击为控制点
    else:
        points_dst.append([x, y])  # 偶数次点击为目标点
    
    # 在图像上标记点（蓝色：控制点，红色：目标点），并画箭头
    marked_image = image.copy()
    for pt in points_src:
        cv2.circle(marked_image, tuple(pt), 1, (255, 0, 0), -1)  # 蓝色表示控制点
    for pt in points_dst:
        cv2.circle(marked_image, tuple(pt), 1, (0, 0, 255), -1)  # 红色表示目标点
    
    # 画出箭头，表示从控制点到目标点的映射
    for i in range(min(len(points_src), len(points_dst))):
        cv2.arrowedLine(marked_image, tuple(points_src[i]), tuple(points_dst[i]), (0, 255, 0), 1)  # 绿色箭头表示映射
    
    return marked_image

# 执行仿射变换

def point_guided_deformation(image, source_pts, target_pts, alpha=1.0, eps=1e-8):
    """ 
    Return
    ------
        A deformed image.
    """
    height, width = image.shape[:2]
    gridX = np.arange(width, dtype=np.int16)
    gridY = np.arange(height, dtype=np.int16)
    xx, yy = np.meshgrid(gridX, gridY)
    
    n = len(source_pts)
    p = source_pts.astype(np.float32).reshape(n, 1, 1, 2)
    q = target_pts.astype(np.float32).reshape(n, 1, 1, 2)
    v = np.dstack((xx, yy))
    
    w = 1.0 / (np.sum((p-v)**2, axis=-1)+eps)**1
    w_norm = w / np.sum(w, axis=0, keepdims=True)
    
    p_star = np.sum(p*w_norm.reshape(-1, height, width, 1), axis=0)
    q_star = np.sum(q*w_norm.reshape(-1, height, width, 1), axis=0)
    
    p_hat = p - p_star
    q_hat = q - q_star
    
    A_1row = np.sum(p_hat[..., 0][..., None] * p_hat * w_norm[..., None], axis=0)
    A_2row = np.sum(p_hat[..., 1][..., None] * p_hat * w_norm[..., None], axis=0)
    
    b_1row = np.sum(p_hat[..., 0][..., None] * q_hat * w_norm[..., None], axis=0)
    b_2row = np.sum(p_hat[..., 1][..., None] * q_hat * w_norm[..., None], axis=0)
    
    A = np.dstack((A_1row, A_2row)).reshape(height, width, 2, 2)
    b = np.dstack((b_1row, b_2row)).reshape(height, width, 2, 2)
    
    A_inv = np.linalg.inv(A)
    M = np.einsum("ijmk,ijkn->ijmn", A_inv, b)
    
    x = v.reshape(height, width, 1, 2) - p_star.reshape(height, width, 1, 2)
    y = np.einsum("ijmk,ijkn->ijmn", x, M) + q_star.reshape(height, width, 1 ,2)
    y = y.reshape(height, width, 2)
    
    map_x = np.zeros((height, width), dtype=np.float32)
    map_y = np.zeros((height, width), dtype=np.float32)

    for j in range(0, int(height)-1):
        for i in range(0, int(width)-1):
            map_x[j,i] = y[j,i][0]
            map_y[j,i] = y[j,i][1]
    mls_img = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR)
    
    warped_image = np.array(mls_img)
    ### FILL: 基于MLS or RBF 实现 image warping

    return warped_image

def run_warping():
    global points_src, points_dst, image ### fetch global variables

    warped_image = point_guided_deformation(image, np.array(points_src), np.array(points_dst))

    return warped_image

# 清除选中点
def clear_points():
    global points_src, points_dst
    points_src.clear()
    points_dst.clear()
    return image  # 返回未标记的原图

# 使用 Gradio 构建界面
with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column():
            input_image = gr.Image(source="upload", label="上传图片", interactive=True, width=800, height=200)
            point_select = gr.Image(label="点击选择控制点和目标点", interactive=True, width=800, height=800)
            
        with gr.Column():
            result_image = gr.Image(label="变换结果", width=800, height=400)
    
    # 按钮
    run_button = gr.Button("Run Warping")
    clear_button = gr.Button("Clear Points")  # 添加清除按钮
    
    # 上传图像的交互
    input_image.upload(upload_image, input_image, point_select)
    # 选择点的交互，点选后刷新图像
    point_select.select(record_points, None, point_select)
    # 点击运行 warping 按钮，计算并显示变换后的图像
    run_button.click(run_warping, None, result_image)
    # 点击清除按钮，清空所有已选择的点
    clear_button.click(clear_points, None, point_select)
    
# 启动 Gradio 应用
demo.launch(server_name="0.0.0.0", share=True)
