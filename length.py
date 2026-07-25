from ursina import *
app = Ursina()
seg = Entity(model='env') 
bounds = seg.model.getTightBounds()
if bounds:
    min_b, max_b = bounds
    print("Segment size (x,y,z):", max_b - min_b)
    print("Segment LENGTH (z):", max_b.z - min_b.z)
else:
    print("Could not get bounds -- check the model name is correct")
application.quit()
app.run()