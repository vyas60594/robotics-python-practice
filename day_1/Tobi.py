sprite = Sprite('Tobi')

import time

motor=QuarkyMiniExpansion()
motor.miniinitialise()

try:
  motor.runmotor('L','1',70)
  time.sleep(5)
  motor.stopmotor('L')
  time.sleep(5)
  motor.runmotor('L','2',70)
  
  time.sleep(5)
  

finally:
  motor.stopmotor('L')

print("task done")
  
  
