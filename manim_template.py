from manimlib import *

class TextHighlightAnimation(Scene):
    def construct(self):
        # 文本和时间数据
        align_words = {align_words}

        word_times_list = []
        curr = []
        for i in range(len(align_words)):
            curr.append(align_words[i])
            if len(' '.join([item['text'] for item in curr])) > 30:
                curr.pop()
                word_times_list.append(curr)
                curr = [align_words[i]]
        if curr:
            word_times_list.append(curr)
        # 根据 word_times_list 的大小调整视频的高度
        height = 6 + len(word_times_list) * 1
        self.camera.frame.set_height(height)

        text = '\n'.join([' '.join([word_time["text"] for word_time in word_times]) for word_times in word_times_list])
        # 创建一个显示播放时间的时钟
        clock = DecimalNumber(0, num_decimal_places=2, include_sign=False, unit="s")
        clock.to_corner(UP + RIGHT)
        self.add(clock)
        # 让时钟开始计时
        clock.add_updater(lambda m, dt: m.increment_value(dt))
        # 将文本分割成单词
        
        text_mob = Text(text).scale(1.5)

        # 直接显示文本（不播放 Write 动画）
        self.add(text_mob)

        # 为每个单词创建高亮效果
        prev = ''
        
        prev_end = 0
        total = 0
        for i, word_times in enumerate(word_times_list):
            for j, word_time in enumerate(word_times):
                
                word = word_time["text"]
                start_time = word_time["start"]
                end_time = word_time["end"]
                if end_time >= 0 and start_time >= 0:
                    if start_time - prev_end > 0.001:
                        k = clock.get_value() - total
                        self.wait(max(0, start_time - prev_end - k))
                        total += start_time - prev_end
                        #print('WAIT', word, round(start_time - prev_end, 2), total, clock.get_value(), k)
                    # 找到单词在文本中的位置
                    k = clock.get_value() - total
                    word_mob = text_mob[len(prev):len(prev)+len(word)]
                    if end_time - start_time - k > 0.2:
                        # 高亮单词
                        self.play(
                            ApplyMethod(word_mob.set_color, RED),
                            rate_func=linear,
                            run_time=max(0, end_time - start_time - k)
                        )
                        total += end_time - start_time
                        #print('PLAY', word, end_time - start_time)
                    else:
                        
                        word_mob.set_color(RED)
                        self.wait(max(0, end_time - start_time - k))
                        total += end_time - start_time
                        #print('NOPLAY', word, end_time - start_time, total, clock.get_value(), k)
                    
                    #self.play(
                    #    ApplyMethod(word_mob.set_color, WHITE),
                    #    rate_func=linear,
                    #    run_time=0.001
                    #)
                    prev_end = end_time
                prev += word
        print('TOTAL', total)
        self.wait()