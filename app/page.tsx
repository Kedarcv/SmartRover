"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Activity,
  MapPin,
  Navigation,
  Radar,
  AlertTriangle,
  Play,
  Square,
  Wifi,
  WifiOff,
  Thermometer,
  Cpu,
  HardDrive,
} from "lucide-react"

// Add near the top of the file, after imports
async function safeFetch<T>(url: string, opts?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, { ...opts, cache: "no-store" })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = (await res.json()) as T
    return (json as any).success === false ? null : (json as T)
  } catch {
    return null
  }
}

interface VehicleData {
  timestamp: number
  position: [number, number]
  heading: number
  sensor_data: {
    ultrasonic: number[]
    camera_available: boolean
  }
  action_data: {
    action: string
    action_confidence: number
    speed: number
    obstacle_detected: boolean
    obstacle_confidence: number
  }
  map_data: {
    robot_position: [number, number]
    robot_heading: number
    path_history: [number, number][]
    obstacles: any[]
    map_region: number[][][]
    timestamp: number
  }
  system_status: {
    running: boolean
    camera_available: boolean
    emergency_stop: boolean
  }
}

interface SystemInfo {
  platform: string
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  temperature: number | null
  uptime: number
  vehicle_running: boolean
}

export default function MiningDashboard() {
  const [vehicleData, setVehicleData] = useState<VehicleData | null>(null)
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [serverUrl, setServerUrl] = useState("http://192.168.1.100:5000")
  const [isLoading, setIsLoading] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const interval = setInterval(() => {
      fetchVehicleData()
      fetchSystemInfo() // will early-exit if not connected
    }, 1000)

    return () => clearInterval(interval)
  }, [serverUrl, isConnected])

  const fetchVehicleData = async () => {
    const result = await safeFetch<{ success: boolean; data: VehicleData }>(`${serverUrl}/api/vehicle-status`)

    if (result?.success) {
      setVehicleData(result.data)
      setIsConnected(true)
    } else {
      setIsConnected(false)
      setVehicleData(null)
    }
  }

  const fetchSystemInfo = async () => {
    if (!isConnected) return

    const result = await safeFetch<{ success: boolean; data: SystemInfo }>(`${serverUrl}/api/system-info`)

    if (result?.success) {
      setSystemInfo(result.data)
    } else {
      setSystemInfo(null)
    }
  }

  const sendVehicleCommand = async (command: string) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${serverUrl}/api/vehicle-control`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ command }),
      })

      const result = await response.json()
      if (result.success) {
        console.log(result.message)
      }
    } catch (error) {
      console.error("Failed to send command:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const drawMap = () => {
    if (!canvasRef.current || !vehicleData?.map_data.map_region) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const mapRegion = vehicleData.map_data.map_region
    const imageData = ctx.createImageData(canvas.width, canvas.height)

    // Convert map data to image data
    for (let y = 0; y < Math.min(canvas.height, mapRegion.length); y++) {
      for (let x = 0; x < Math.min(canvas.width, mapRegion[y]?.length || 0); x++) {
        const pixelIndex = (y * canvas.width + x) * 4
        const mapValue = mapRegion[y][x]

        if (Array.isArray(mapValue) && mapValue.length >= 3) {
          imageData.data[pixelIndex] = mapValue[0] // R
          imageData.data[pixelIndex + 1] = mapValue[1] // G
          imageData.data[pixelIndex + 2] = mapValue[2] // B
          imageData.data[pixelIndex + 3] = 255 // A
        } else {
          // Grayscale value
          const value = typeof mapValue === "number" ? mapValue : 0
          imageData.data[pixelIndex] = value
          imageData.data[pixelIndex + 1] = value
          imageData.data[pixelIndex + 2] = value
          imageData.data[pixelIndex + 3] = 255
        }
      }
    }

    ctx.putImageData(imageData, 0, 0)
  }

  useEffect(() => {
    drawMap()
  }, [vehicleData])

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Underground Mining Vehicle Dashboard</h1>
            <p className="text-gray-400">Real-time monitoring and control system</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Label htmlFor="server-url" className="text-sm">
                Server URL:
              </Label>
              <Input
                id="server-url"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                className="w-48 bg-gray-800 border-gray-600"
                placeholder="http://192.168.1.100:5000"
              />
            </div>
            <Badge variant={isConnected ? "default" : "destructive"} className="flex items-center gap-1">
              {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {isConnected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
        </div>

        {/* Control Panel */}
        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle>Vehicle Control</CardTitle>
            <CardDescription>Remote control and emergency functions</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-4">
            <Button
              onClick={() => sendVehicleCommand("start")}
              disabled={isLoading || !isConnected}
              className="flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Vehicle
            </Button>
            <Button
              onClick={() => sendVehicleCommand("stop")}
              disabled={isLoading || !isConnected}
              variant="outline"
              className="flex items-center gap-2"
            >
              <Square className="w-4 h-4" />
              Stop Vehicle
            </Button>
            <Button
              onClick={() => sendVehicleCommand("emergency_stop")}
              disabled={isLoading || !isConnected}
              variant="destructive"
              className="flex items-center gap-2"
            >
              <AlertTriangle className="w-4 h-4" />
              Emergency Stop
            </Button>
          </CardContent>
        </Card>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-gray-800 border-gray-700">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Current Action</CardTitle>
              <Navigation className="h-4 w-4 text-blue-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-400">
                {vehicleData?.action_data.action?.toUpperCase() || "N/A"}
              </div>
              <p className="text-xs text-gray-400">
                Confidence: {((vehicleData?.action_data.action_confidence || 0) * 100).toFixed(1)}%
              </p>
            </CardContent>
          </Card>

          <Card className="bg-gray-800 border-gray-700">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Speed</CardTitle>
              <Activity className="h-4 w-4 text-green-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-400">
                {((vehicleData?.action_data.speed || 0) * 100).toFixed(1)}%
              </div>
              <Progress value={(vehicleData?.action_data.speed || 0) * 100} className="mt-2" />
            </CardContent>
          </Card>

          <Card className="bg-gray-800 border-gray-700">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Position</CardTitle>
              <MapPin className="h-4 w-4 text-purple-400" />
            </CardHeader>
            <CardContent>
              <div className="text-lg font-bold text-purple-400">
                X: {vehicleData?.position[0]?.toFixed(1) || "0.0"}
              </div>
              <div className="text-lg font-bold text-purple-400">
                Y: {vehicleData?.position[1]?.toFixed(1) || "0.0"}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gray-800 border-gray-700">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Status</CardTitle>
              <Activity
                className={`h-4 w-4 ${vehicleData?.system_status.running ? "text-green-400" : "text-red-400"}`}
              />
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${vehicleData?.system_status.running ? "text-green-400" : "text-red-400"}`}
              >
                {vehicleData?.system_status.running ? "RUNNING" : "STOPPED"}
              </div>
              <p className="text-xs text-gray-400">
                Camera: {vehicleData?.sensor_data.camera_available ? "Available" : "Unavailable"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* System Information */}
        {systemInfo && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-gray-800 border-gray-700">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
                <Cpu className="h-4 w-4 text-orange-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-400">{systemInfo.cpu_percent.toFixed(1)}%</div>
                <Progress value={systemInfo.cpu_percent} className="mt-2" />
              </CardContent>
            </Card>

            <Card className="bg-gray-800 border-gray-700">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Memory</CardTitle>
                <HardDrive className="h-4 w-4 text-cyan-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-cyan-400">{systemInfo.memory_percent.toFixed(1)}%</div>
                <Progress value={systemInfo.memory_percent} className="mt-2" />
              </CardContent>
            </Card>

            <Card className="bg-gray-800 border-gray-700">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Temperature</CardTitle>
                <Thermometer className="h-4 w-4 text-red-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-400">
                  {systemInfo.temperature ? `${systemInfo.temperature.toFixed(1)}°C` : "N/A"}
                </div>
                <p className="text-xs text-gray-400">CPU Temperature</p>
              </CardContent>
            </Card>

            <Card className="bg-gray-800 border-gray-700">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Uptime</CardTitle>
                <Activity className="h-4 w-4 text-green-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-400">{formatUptime(systemInfo.uptime)}</div>
                <p className="text-xs text-gray-400">System Uptime</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SLAM Map */}
          <Card className="bg-gray-800 border-gray-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="w-5 h-5" />
                SLAM Map & Path
              </CardTitle>
              <CardDescription>Real-time mapping with vehicle path</CardDescription>
            </CardHeader>
            <CardContent>
              <canvas
                ref={canvasRef}
                width={400}
                height={300}
                className="border border-gray-600 rounded w-full bg-black"
              />
              <div className="mt-2 text-sm text-gray-400">
                Path points: {vehicleData?.map_data.path_history?.length || 0} | Obstacles:{" "}
                {vehicleData?.map_data.obstacles?.length || 0}
              </div>
            </CardContent>
          </Card>

          {/* Sensor Data */}
          <Card className="bg-gray-800 border-gray-700">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Radar className="w-5 h-5" />
                Ultrasonic Sensors
              </CardTitle>
              <CardDescription>Real-time distance measurements</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {["Front", "Left", "Right", "Rear"].map((direction, index) => {
                const distance = vehicleData?.sensor_data.ultrasonic[index] || 0
                const isObstacle = distance < 50
                return (
                  <div key={direction} className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm font-medium">{direction}</span>
                      <span className={`text-sm ${isObstacle ? "text-red-400" : "text-gray-400"}`}>
                        {distance.toFixed(1)} cm
                      </span>
                    </div>
                    <Progress value={(distance / 400) * 100} className={`h-2 ${isObstacle ? "bg-red-900" : ""}`} />
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>

        {/* Obstacle Detection Status */}
        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle
                className={`w-5 h-5 ${vehicleData?.action_data.obstacle_detected ? "text-red-400" : "text-green-400"}`}
              />
              Obstacle Detection & Navigation
            </CardTitle>
            <CardDescription>AI decision making and sensor fusion</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <h4 className="font-medium">Current Decision</h4>
                <div className="text-2xl font-bold text-blue-400">
                  {vehicleData?.action_data.action?.toUpperCase() || "N/A"}
                </div>
                <Progress value={(vehicleData?.action_data.action_confidence || 0) * 100} className="h-2" />
                <p className="text-xs text-gray-400">
                  Confidence: {((vehicleData?.action_data.action_confidence || 0) * 100).toFixed(1)}%
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="font-medium">Speed Control</h4>
                <div className="text-2xl font-bold text-green-400">
                  {((vehicleData?.action_data.speed || 0) * 100).toFixed(0)}%
                </div>
                <Progress value={(vehicleData?.action_data.speed || 0) * 100} className="h-2" />
                <p className="text-xs text-gray-400">Motor Speed</p>
              </div>

              <div className="space-y-2">
                <h4 className="font-medium">Obstacle Status</h4>
                <div
                  className={`text-2xl font-bold ${vehicleData?.action_data.obstacle_detected ? "text-red-400" : "text-green-400"}`}
                >
                  {vehicleData?.action_data.obstacle_detected ? "DETECTED" : "CLEAR"}
                </div>
                <Progress value={(vehicleData?.action_data.obstacle_confidence || 0) * 100} className="h-2" />
                <p className="text-xs text-gray-400">
                  Confidence: {((vehicleData?.action_data.obstacle_confidence || 0) * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
