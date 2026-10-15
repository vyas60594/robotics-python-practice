
import time

# Initialize Quarky Intellio
intellio = QuarkyIntellio()

# Move servo to starting position
intellio.moveservointime("S1", 39, 1)
time.sleep(1)

# # Move from 0 to 180 degrees in 10 seconds
# intellio.moveservointime("S1", 180, 1)

# # Move from 180 to 0 degrees in 10 seconds
# intellio.moveservointime("S1", 0, 1)

intellio.moveservointime("S1", 90, 1)


print("Servo movement completed!")
