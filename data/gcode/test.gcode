%
( Sample G-Code für 3-Achs CNC )
G21         ; Einheiten in Millimeter
G17         ; XY-Ebene auswählen
G90         ; Absoluter Programmiermodus
G94         ; Vorschub pro Minute

( Werkzeug und Spindel starten )
T1 M6       ; Werkzeugwechsel auf Werkzeug 1
S1000 M3    ; Spindel mit 1000 U/min im Uhrzeigersinn starten
G54         ; Nullpunktverschiebung aktivieren

( Anfahren der Startposition )
G0 X0 Y0 Z5 ; Schnellfahrt zu Startpunkt, Z=5 mm über Werkstück
G1 Z-2 F100 ; Zustellung in Z, 2 mm tief mit Vorschub 100 mm/min

( Quadrat fräsen )
G1 X200 Y0 F200   ; Erste Seite
G1 X200 Y200       ; Zweite Seite
G1 X0  Y200       ; Dritte Seite
G1 X0  Y0        ; Vierte Seite zurück zum Start
G1 X0 Y200

( Werkzeug zurückziehen )
G0 Z5        ; Werkzeug hochfahren
M5           ; Spindel stoppen
G0 X0 Y0     ; Zurück zur Nullposition
M30          ; Programmende und Rücksetzen
%
