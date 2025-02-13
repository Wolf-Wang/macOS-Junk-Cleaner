#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, platform, subprocess, shutil, tkinter as tk
from tkinter import ttk, filedialog, messagebox

class CleanerApp:
    def __init__(self):
        # 创建主窗口
        self.root = tk.Tk()
        self.root.geometry("1200x700")
        self.root.minsize(900, 600)

        # 设置主窗口标题
        self.root.title(f"macOS Junk Cleaner - Build: 250213 Python: {sys.version.split()[0]}")
        if os.geteuid() == 0:
            self.root.title(self.root.title() + " (Running as root)")

        # 绑定关闭窗口事件到 on_closing 方法
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 初始化中断标志
        self.aborted = False

        # 定义垃圾文件特征
        self.junk_files = {
            'names': [".DS_Store", "desktop.ini", "Thumbs.db", ".zsh_history", ".viminfo", ".localized"],
            'extensions': ['.log', '.tmp', '.cache'],
            'folders': ["$RECYCLE.BIN", "Caches", "Logs", "CrashReporter", "tmp", "temp", "log", ".Trash", ".fseventsd", ".Spotlight-V100", "Photo Booth Library"]
        }

        # 设置按钮和文件列表样式
        style = ttk.Style()
        style.configure("Action.TButton", padding=5, width=5)
        style.configure("Treeview", rowheight=25)

        # 创建路径label
        path_label = ttk.Label(self.root, text="Path to scan: ")
        path_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # 创建路径输入框
        self.path_entry = ttk.Entry(self.root)
        self.path_entry.insert(0, "/Users")
        self.path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 创建浏览按钮
        browse_btn = ttk.Button(self.root, text="Browse", command=self.browse_path, style="Action.TButton")
        browse_btn.grid(row=0, column=2, padx=5, pady=5)

        # 创建扫描按钮
        self.scan_btn = ttk.Button(self.root, text="Scan", command=self.scan_files, style="Action.TButton")
        self.scan_btn.grid(row=0, column=3, padx=5, pady=5)

        # 创建清理按钮
        self.clean_btn = ttk.Button(self.root, text="Clean", command=self.clean_files, style="Action.TButton")
        self.clean_btn.grid(row=0, column=4, padx=5, pady=5)

        # 创建文件列表区域
        self.tree = ttk.Treeview(self.root, columns=("select", "path", "size", "modified"), show="headings")

        # 设置列标题
        self.tree.heading("select", text="☑")
        self.tree.heading("path", text="Path", command=lambda: self.treeview_sort_column("path", False))
        self.tree.heading("size", text="Size", command=lambda: self.treeview_sort_column("size", False))
        self.tree.heading("modified", text="Modified", command=lambda: self.treeview_sort_column("modified", False))

        # 设置列宽
        self.tree.column("select", width=10, anchor="center")
        self.tree.column("path", width=700)
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("modified", width=100, anchor="center")

        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=1, column=0, columnspan=5, sticky="nsew", padx=5, pady=5)
        scrollbar.grid(row=1, column=5, sticky="ns")

        # 创建状态栏
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", padding=(5, 2))
        status_bar.grid(row=2, column=0, columnspan=6, sticky="ew")

        # 配置网格权重
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Open", command=self.open_file)
        self.context_menu.add_command(label="Open in Finder", command=self.open_in_finder)
        self.context_menu.add_command(label="Copy as Path", command=self.copy_path)

        # 右键菜单绑定到文件列表
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 绑定鼠标左键点击事件
        self.tree.bind("<Button-1>", self.handle_click)

        # 程序启动后100ms自动开始首次扫描
        self.root.after(100, self.scan_files)

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def scan_files(self):
        # 扫描进行时禁用扫描按钮和清理按钮
        self.scan_btn.config(state='disabled')
        self.clean_btn.config(state='disabled')

        # 清空现有内容
        for item in self.tree.get_children():
            self.tree.delete(item)

        start_time = time.time()
        total_size = 0
        file_count = 0

        scan_path = os.path.expanduser(self.path_entry.get())

        for root, dirs, files in os.walk(scan_path):
            # 检查是否已中止执行
            if self.aborted:
                break

            # 更新状态栏
            self.status_var.set(f"Scanning: {root}")
            self.root.update()

            # 检查文件夹名称
            for folder in dirs[:]:
                if folder in self.junk_files['folders']:
                    full_path = os.path.join(root, folder)
                    size = self.get_dir_size(full_path)
                    modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(full_path)))
                    self.tree.insert("", "end", values=("✓", full_path, self.format_size(size), modified))
                    total_size += size
                    file_count += 1

            # 检查文件
            for file in files:
                full_path = os.path.join(root, file)

                # 检查文件名和扩展名
                if (file in self.junk_files['names'] or os.path.splitext(file)[1] in self.junk_files['extensions']):
                    try:
                        size = os.path.getsize(full_path)
                        modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(full_path)))
                        self.tree.insert("", "end", values=("✓", full_path, self.format_size(size), modified))
                        total_size += size
                        file_count += 1
                    except (OSError, PermissionError):
                        continue

        # 如果执行被中止，则不更新状态栏和按钮状态
        if not self.aborted:
            elapsed_time = time.time() - start_time
            self.status_var.set(f"Scan completed in {elapsed_time:.2f}s. Found {file_count} items, Total size: {self.format_size(total_size)}")
            self.update_clean_btn_state()
            self.scan_btn.config(state='normal')

    def clean_files(self):
        selected_items = []
        for item in self.tree.get_children():
            if self.tree.item(item)['values'][0] == "✓":
                selected_items.append(item)

        if not selected_items:
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to delete these files?"):
            for item in selected_items:
                values = self.tree.item(item)['values']
                path = values[1]
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    else:
                        try:
                            shutil.rmtree(path)
                        except (OSError, PermissionError) as e:
                            # 如果无法直接删除目录，尝试逐个删除内部文件和子目录
                            for root, dirs, files in os.walk(path, topdown=False):
                                for name in files:
                                    try:
                                        os.remove(os.path.join(root, name))
                                    except (OSError, PermissionError):
                                        continue
                                for name in dirs:
                                    try:
                                        os.rmdir(os.path.join(root, name))
                                    except (OSError, PermissionError):
                                        continue
                            # 最后尝试删除空目录
                            try:
                                os.rmdir(path)
                            except (OSError, PermissionError):
                                self.status_var.set(f"Could not completely remove directory: {path}")
                                continue
                    self.tree.delete(item)
                except (OSError, PermissionError) as e:
                    self.status_var.set(f"Error deleting {path}: {str(e)}")
                    continue

            self.status_var.set("Cleanup completed")
            self.update_clean_btn_state()

    def update_clean_btn_state(self):
        has_checked = False
        for item in self.tree.get_children():
            if self.tree.item(item)['values'][0] == "✓":
                has_checked = True
                break
        self.clean_btn.config(state='normal' if has_checked else 'disabled')

    def handle_click(self, event):
        """
        处理鼠标点击事件
        参数:
            event: 鼠标事件对象
        功能:
            - 处理复选框列的点击
            - 处理表头复选框的全选/取消全选
            - 更新界面状态
        返回值:
            Boolean: 是否处理了点击事件
        """
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)

        if column == "#1":  # 复选框列
            if region == "heading":
                self.toggle_all()
                return True
            elif region == "cell":
                item = self.tree.identify_row(event.y)
                if item:
                    values = list(self.tree.item(item)["values"])
                    values[0] = " " if values[0] == "✓" else "✓"
                    self.tree.item(item, values=values)
                    self.update_header_state()
                    self.update_clean_btn_state()
                return True
        return False

    def toggle_all(self):
        """处理全选/取消全选"""
        if not self.tree.get_children():
            return

        first_item = self.tree.get_children()[0]
        all_checked = self.tree.item(first_item)["values"][0] == "✓"
        new_state = " " if all_checked else "✓"

        # 更新表头状态
        self.tree.heading("select", text="☑" if new_state == "✓" else "☐")

        # 更新所有项目
        for item in self.tree.get_children():
            values = list(self.tree.item(item)["values"])
            values[0] = new_state
            self.tree.item(item, values=values)

        self.update_clean_btn_state()

    def update_header_state(self):
        """
        更新表头复选框状态
        - 检查是否有文件列表项
        - 检查所有项目是否都被选中
        - 更新表头复选框显示状态（☑ 或 ☐）
        """
        if not self.tree.get_children():
            self.tree.heading("select", text="☐")
            return

        all_checked = True
        for item in self.tree.get_children():
            if self.tree.item(item)["values"][0] != "✓":
                all_checked = False
                break

        self.tree.heading("select", text="☑" if all_checked else "☐")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def open_file(self):
        selected = self.tree.selection()
        if selected:
            path = self.tree.item(selected[0])['values'][1]
            if platform.system() == 'Darwin':
                subprocess.run(['open', path])

    def open_in_finder(self):
        selected = self.tree.selection()
        if selected:
            path = self.tree.item(selected[0])['values'][1]
            if platform.system() == 'Darwin':
                subprocess.run(['open', '-R', path])

    def copy_path(self):
        selected = self.tree.selection()
        if selected:
            path = self.tree.item(selected[0])['values'][1]
            self.root.clipboard_clear()
            self.root.clipboard_append(path)

    @staticmethod
    def get_dir_size(path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    continue
        return total_size

    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def treeview_sort_column(self, col, reverse):
        """排序 treeview 的列"""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]

        # 根据列类型进行不同的排序
        if col == "size":
            # 将大小字符串转换为字节数进行排序
            def convert_size_to_bytes(size_str):
                units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                number = float(size_str.split()[0])
                unit = size_str.split()[1]
                return number * units[unit]

            items = [(convert_size_to_bytes(self.tree.set(k, col)), k) for k in self.tree.get_children('')]
        elif col == "modified":
            # 日期时间排序
            import datetime
            items = [(datetime.datetime.strptime(self.tree.set(k, col), '%Y-%m-%d %H:%M:%S'), k)
                    for k in self.tree.get_children('')]

        # 排序
        items.sort(reverse=reverse)

        # 重新排列项目
        for index, (_, k) in enumerate(items):
            self.tree.move(k, '', index)

        # 切换排序方向
        self.tree.heading(col, command=lambda: self.treeview_sort_column(col, not reverse))

        # 更新表头文字，添加排序指示器
        for header in ["path", "size", "modified"]:
            if header == col:
                text = self.tree.heading(header)["text"].rstrip(" ↑↓")
                self.tree.heading(header, text=f"{text} {'↓' if reverse else '↑'}")
            else:
                text = self.tree.heading(header)["text"].rstrip(" ↑↓")
                self.tree.heading(header, text=text)

    def run(self):
        self.root.mainloop()

    def on_closing(self):
        # 设置中断标志，让 clean_files 方法检测到后停止扫描
        self.aborted = True
        # 退出程序
        self.root.quit()

if __name__ == "__main__":
    app = CleanerApp()
    app.run()
