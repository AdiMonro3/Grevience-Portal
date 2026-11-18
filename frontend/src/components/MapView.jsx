import { useEffect } from "react";
import { CircleMarker, MapContainer, Polygon, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";

// Tiles come from OpenStreetMap (free, no key) and need internet.
// Every page that shows a map also has a list/text fallback for offline demos.

function Recenter({ center, zoom }) {
  const map = useMap();
  const [lat, lng] = center;
  useEffect(() => {
    map.setView([lat, lng], zoom ?? map.getZoom());
  }, [map, lat, lng, zoom]);
  return null;
}

function ClickHandler({ onClick }) {
  useMapEvents({ click: (e) => onClick(e.latlng.lat, e.latlng.lng) });
  return null;
}

/**
 * markers:  [{ id, lat, lng, color, radius, popup, tooltip }]
 * polygons: [{ id, positions: [[lat, lng], ...], label }]
 */
export default function MapView({ center, zoom = 14, markers = [], polygons = [], onMapClick, className = "h-80" }) {
  return (
    <div className={`relative z-0 overflow-hidden rounded-xl border border-slate-200 ${className}`}>
      <MapContainer center={center} zoom={zoom} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {polygons.map((p) => (
          <Polygon key={p.id} positions={p.positions} pathOptions={{ color: "#475569", weight: 1, dashArray: "4", fillOpacity: 0.04 }}>
            {p.label && <Tooltip sticky>{p.label}</Tooltip>}
          </Polygon>
        ))}
        {markers.map((m) => (
          <CircleMarker
            key={m.id}
            center={[m.lat, m.lng]}
            radius={m.radius || 9}
            pathOptions={{ color: "#ffffff", weight: 2, fillColor: m.color || "#1d4ed8", fillOpacity: 0.95 }}
          >
            {m.tooltip && <Tooltip>{m.tooltip}</Tooltip>}
            {m.popup && <Popup>{m.popup}</Popup>}
          </CircleMarker>
        ))}
        <Recenter center={center} zoom={zoom} />
        {onMapClick && <ClickHandler onClick={onMapClick} />}
      </MapContainer>
    </div>
  );
}
