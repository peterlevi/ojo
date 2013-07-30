from gi.repository import Clutter, ClutterGst, Gst
import sys

ClutterGst.init(sys.argv)

stage = Clutter.Stage()
stage.set_size(800, 600)
stage.connect('destroy', lambda x: Clutter.main_quit())

texture = Clutter.Texture()
pipeline = Gst.parse_launch("playbin2 uri=http://docs.gstreamer.com/media/sintel_trailer-480p.webm")
sink = Gst.ElementFactory.make("autocluttersink", None)
sink.set_property("texture", texture)
pipeline.set_property("video-sink", sink)
Gst.Element.set_state(pipeline, Gst.State.PLAYING)

stage.add_actor(texture)
#texture.set_opacity(0)

timeline = Clutter.Timeline()
timeline.set_duration(2500)
#timeline.set_delay(50)
timeline.set_loop(False)
alpha = Clutter.Alpha()
alpha.set_timeline(timeline)
alpha.set_func(lambda a, d: a.get_timeline().get_progress(), None)
behaviour = Clutter.BehaviourRotate(alpha=alpha, angle_start=180, angle_end=0, axis=Clutter.RotateAxis.Y_AXIS, direction = "ccw")
behaviour.apply(texture)
timeline.start()

stage.show_all()
#texture.animatev(Clutter.AnimationMode.EASE_OUT_SINE, 2500, ["opacity"], [255])

Clutter.main()