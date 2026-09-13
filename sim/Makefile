# iverilog によるシミュレーション。`make MODE=1 FRAME=3` のように指定できる。
MODE  ?= 9
FRAME ?= 2
HDL   := ../hdl
SRCS  := $(HDL)/video_timing.v $(HDL)/frame_counter.v $(HDL)/text_overlay.v $(HDL)/pattern_gen.v \
         $(HDL)/mmcm_pixclk.v $(HDL)/hdmi_channel.v tb_channel.v

frame.ppm: $(SRCS) $(HDL)/font8x16.mem
	cp $(HDL)/font8x16.mem .
	iverilog -g2012 -DSIM -I$(HDL) -Ptb_channel.MODE=$(MODE) -Ptb_channel.FRAME=$(FRAME) -o sim.vvp $(SRCS)
	vvp sim.vvp

clean:
	rm -f sim.vvp frame.ppm font8x16.mem
.PHONY: clean
