
9

110%
SD -::- Práctica EVCharging -::- Curso 25/26 Release 1  
 
1 
 
SD Sistemas Distribuidos 
25/26 Práctica no guiada: Sockets, Streaming de Eventos, 
Colas y modularidad.   
 EVCharging Network 
Preámbulo 
El objetivo de esta práctica es que los estudiantes extiendan y afiancen sus 
conocimientos sobre el uso de la tecnología de comunicación básica sockets, estudiada durante 
las sesiones de teoría. 
Los sockets son la base de las comunicaciones entre computadores y suponen el punto 
de  enlace  básico  entre  nuestra  aplicación  e  Internet,  utilizando  muy  pocos  recursos  de  red. 
Como  contrapartida,  las  aplicaciones  que  utilizan  sockets  como  mecanismo  de  comunicación 
deben  interpretar  los  mensajes  que  intercambian  entre  sí,  es  decir,  deben  establecer  un 
protocolo o acuerdo de comunicación entre ellos. Esta necesidad implica un fuerte 
acoplamiento  entre  las  aplicaciones  distribuidas  que  utilizan  sockets  como  mecanismo  de 
comunicación, ya que todas las partes deben conocer de antemano la estructura de los mensajes 
que serán intercambiados y codificarlo en su programación. 
Por  otro  lado,  otras  tecnologías  y  arquitecturas  actuales  orientadas  al  streaming  de 
eventos en tiempo real, basadas en sockets pero de más alto nivel en términos de construcción 
y desarrollo, permiten la implementación de soluciones menos acopladas y más resilientes que 
estos. 
Esta  práctica  establece  el  marco  inicial  de  un  desarrollo  que  se  ampliará  durante  el 
cuatrimestre y que permitirá al estudiante crear una aplicación similar a las que se desarrollan 
hoy en día en los entornos empresariales, poniendo el foco en el uso e integración de distintos 
paradigmas de comunicación susceptibles de ser utilizados. 
  
SD -::- Práctica EVCharging -::- Curso 25/26 Release 1  
 
8 
 
apartados anteriores. La aplicación del conductor igualmente mostrará esos estados 
del CP que le está suministrando. 
 
9- Finalizado  el  suministro  mediante  una  opción  de  menú  en  el  CP  que  simula  el 
desenchufado  del  vehículo  del  CP,  este  lo  notificará  a  CENTRAL  quien  a  su  vez 
enviará el “ticket” final al conductor2. El CP volverá al estado de reposo a la espera 
de una nueva petición de suministro. 
 
10- Durante todo el funcionamiento del sistema, el punto de recarga, desde su módulo 
de monitorización estará comprobando el estado de salud del punto de recarga. En 
caso de avería, notificará a CENTRAL dicha situación. En caso de que la contingencia 
se resuelva, el monitor enviarán un nuevo mensaje a CENTRAL y el punto de recarga 
volverá a estar disponible. Si la avería se produjera durante un suministro, este debe 
finalizar inmediatamente  informando a todos los módulos y aplicaciones  de  dicha 
situación. Toda la información tiene que ser claramente visible en pantalla tanto 
de CENTRAL como del monitor del punto de recarga. 
 
11- CENTRAL recibirá todos los estados y suministros de todos los CPs. Los conductores 
solo recibirán los mensajes del CP específico que les esté proporcionando un servicio 
pero también podrán ver todos los CPs que estén disponibles para suministrar. 
 
12- Cuando  un  suministro  concluya,  si  dicho  conductor  precisa  de  otro  servicio  (tiene 
más registros en su fichero) el sistema esperará 4 segundos y procederá a solicitar 
un nuevo servicio. 
 
13- CENTRAL permanecerá siempre en funcionamiento a la espera de nuevas peticiones 
de  suministros.  Adicionalmente  dispondrá  de  opciones  para,  de  forma  arbitraria, 
poder enviar a uno o todos los CPs cualquiera de estas opciones: 
a. Parar: El CP finalizará cualquier suministro si estuviera en ejecución y pondrá 
su estado en ROJO mostrando el mensaje de “Fuera de Servicio”. 
b. Reanudar: El CP volverá a estado ACTIVADO y pondrá su color en VERDE. 
La acción se va desarrollando de forma asíncrona, es decir, sin “turnos”, de manera que 
cada conductor, CENTRAL y cada CP envían mensajes o peticiones de suministros en cualquier 
momento. 
   
 2  En un suministro de un sistema real se habría incorporado todo un flujo de identificación y autorización o denegación 
del sistema de pago mediante integración con pasaralela de pago. Los mecanismos de interconexión con esto sistema 
se han ido realizando a lo largo de los años tanto en sistemas basados en sockets como en llamadas a API’s (tecnología 
que veremos en la segunda parte de la práctica). A efectos de esta práctica, dado el plazo limitado disponible para su 
desarrollo, omitiremos este módulo. 
SD -::- Práctica EVCharging -::- Curso 25/26 Release 1  
 
9 
 
Diseño técnico 
Se propone al estudiante implementar un sistema distribuido compuesto, al menos, de 
los siguientes componentes software:  
   
Figura 2. Arquitectura conceptual del Sistema software, interconexiones entre los componentes y tipos 
de interfaces. Release 1 
Los componentes software que el estudiante ha de desarrollar son los siguientes: 
- Core System: Módulos centrales de la solución. 
o CENTRAL:  Módulo  que  representa  la  central  de  control  de  toda  la  solución. 
Implementa la lógica y gobierno de todo el sistema. 
 
- Charging Point (CP): Módulos que simulan los puntos de recarga 
o Engine:  Módulo  que  recibe  la  información  de  los  sensores  y  se  conecta  al 
sistema central. 
o Monitor:  Módulo  que  monitoriza  la  salud  de  todo  el  punto  de  recarga  y  que 
reporta a la CENTRAL cualquier avería de este. Sirve igualmente para autenticar 
y registrar a los CP en la central cuando sea oportuno. 
 
- Driver: Aplicación que usan los consumidores para usar los puntos de recarga. 
Los componentes pueden ser desarrollados en el lenguaje de preferencia del estudiante: Java, 
C/C++,  .  NET,  Python,  etc.  asumiendo  el  estudiante  la  responsabilidad  de  su  conocimiento  y 
forma de desplegarlo en el laboratorio.  
El subsistema de  gestión de  streaming de  eventos será implementado mediante  la tecnología 
KAFKA cuyo funcionamiento se explicará en las sesiones de prácticas. 
SD -::- Práctica EVCharging -::- Curso 25/26 Release 1  
 
10 
 
A continuación, se especifica más detalladamente cada componente. 
CORE 
Contiene todos los módulos que implementan la estructura principal del sistema.  
CENTRAL: 
Se trata de la aplicación que implementará la lógica fundamental del sistema. El nombre 
de la aplicación será obligatoriamente “EV_Central”. Para su ejecución recibirá por la línea de 
parámetros al menos los siguientes argumentos: 
o Puerto de escucha 
o IP y puerto del Broker/Bootstrap-server del gestor de colas. 
o IP y puerto de la BBDD (solo en caso de que sea necesario) 
Al arrancar la aplicación quedará a la escucha en el puerto establecido e implementará 
todas las funcionalidades necesarias para ejecutar la mecánica de  la solución expresada en el 
apartado anterior incluidas las indicadas en el punto 13 del apartado “Mecánica de la solución”. 
Base de Datos: 
Contendrá, los datos de los conductores, CPs (Id,  estado,...)  así  cualquier  otra 
información que los estudiantes consideren necesaria para la implementación del sistema. 
Los  estudiantes  podrán  decidir  el  motor  de  BD  a  implementar  recomendando  los 
profesores los siguientes: SQlite, MySQL, SQLServer o MongoDB. Igualmente será posible usar 
simples ficheros para la implementación. 
 
Charging Point (CP) 
 Engine: 
Se  trata  de  la  aplicación  que  implementará  la  lógica  principal  de  todo  el  sistema.  El 
nombre  de  la  aplicación  será  obligatoriamente “EV_CP_E”.  Para  su  ejecución  recibirá  por  la 
línea de parámetros al menos los siguientes argumentos: 
o IP y puerto del Broker/Bootstrap-server del gestor de colas. 
o IP y Puerto del EV_M. 
Al arrancar la aplicación, esta se conectará al EC_Central para autenticarse y validar que 
el  vehículo  está  operativo  y  preparado  para  prestar  servicios.  La  aplicación  permanecerá  a  la 
espera  hasta  recibir  una  solicitud  de  servicio  procedente  de  la  central.  El  conductor  quedará 
asignado con el ID recibido en la línea de parámetros y cuya validez deberá ser confirmada por 
EC_Central en el proceso de autenticación.  
Monitor: 
Aplicación que simula un módulo de gestión de observación de todo el CP (hardware y 
software) velando por la seguridad y correcto funcionamiento de este sin incidencias. El nombre 
SD -::- Práctica EVCharging -::- Curso 25/26 Release 1  
 
11 
 
de  la  aplicación  será  obligatoriamente “EC_CP_M”.  Para  su  ejecución  recibirá  por  la  línea  de 
parámetros al menos los siguientes argumentos: 
o IP y puerto del EV_CP_E 
o IP y puerto del EV_Central 
o ID del CP: Identificador único con que ese CP está dado de alta en la red. 
 
Al arrancar la aplicación esta se conectará al Engine del CP al que pertenece y empezará 
a  enviarle  cada  segundo  un  mensaje  de  comprobación  de  estado  de  salud.  Si  no  se  recibe 
respuesta desde el EV_CP_E o se recibe una respuesta tipo KO, EV_CP_M enviará a EV_Central 
un  mensaje  de  avería  como  se  ha  indicado  en  anteriores  apartados.  Para  simular  dichas 
incidencias,  la  aplicación  EV_CP_E  deberá  permitir  que,  en  tiempo  de  ejecución,  se  pulse  una 
tecla para reportar un KO al monitor. 
 
DRIVERS 
Aplicación que disponen los usuarios del sistema para solicitar un suministro. El nombre 
de  la aplicación será  obligatoriamente “EV_Driver”. Para su ejecución recibirá por la línea  de 
parámetros al menos los siguientes argumentos: 
o IP y puerto del Broker/Bootstrap-server del gestor de colas. 
o ID  del  cliente:  Identificador  único  con  que  ese  cliente  está  dado  de  alta  en 
CENTRAL. 
Esta aplicación, además de poder solicitar un suministro puntualmente en un CP, podrá 
leer un fichero todos los servicios que va a solicitar. Enviará el primero a EC_Central y, tras su 
conclusión (sea en éxito o fracaso), esperará 4 segundos y pasará a solicitar el siguiente servicio. 
  
