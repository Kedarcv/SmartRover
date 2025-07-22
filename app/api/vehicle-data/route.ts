import { type NextRequest, NextResponse } from "next/server"

// In-memory storage for demo (use a database in production)
let latestVehicleData: any = null
const dataHistory: any[] = []

export async function POST(request: NextRequest) {
  try {
    const data = await request.json()

    // Store the latest data
    latestVehicleData = {
      ...data,
      receivedAt: new Date().toISOString(),
    }

    // Add to history (keep last 1000 entries)
    dataHistory.push(latestVehicleData)
    if (dataHistory.length > 1000) {
      dataHistory.shift()
    }

    console.log("Received vehicle data:", {
      timestamp: data.timestamp,
      position: data.position,
      action: data.action_data?.action,
      obstacle_detected: data.action_data?.obstacle_detected,
    })

    return NextResponse.json({
      success: true,
      message: "Data received successfully",
    })
  } catch (error) {
    console.error("Error processing vehicle data:", error)
    return NextResponse.json({ success: false, error: "Failed to process data" }, { status: 500 })
  }
}

export async function GET() {
  return NextResponse.json({
    latest: latestVehicleData,
    history: dataHistory.slice(-100), // Return last 100 entries
    totalEntries: dataHistory.length,
  })
}
